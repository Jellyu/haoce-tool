/**
 * 好策APP自动阅读脚本（修正版 v2.6.1）
 * 基于 haoce_auto.js v2.6 的最小修改版，原文件保留未动。
 *
 * 修改点（对应诊断证据）：
 *  M1 auto.waitFor() 改为限时等待并给出明确提示，避免无限卡死。
 *  M2 截图一律 images.copy(captureScreen())，不再 recycle 缓存原图
 *     （原脚本 recycle 的是 ScreenCapturer 的共享缓存图，导致 before/after
 *      是同一张图，相似度恒为 100%）。
 *  M3 滑动坐标改用「当前截图的实际宽高」而不是 device.width/height：
 *     MuMu 的自然方向是横屏，device.width/height 恒为 1600x900，不随旋转变化；
 *     而手势坐标按当前旋转帧解释（好策竖屏时为 900x1600），两者错位导致
 *     滑动落在屏幕边缘/出界、页面不动。截图尺寸随旋转变化，是唯一可靠来源。
 *  M4 gesture() 的「无障碍服务已启用但并未运行」异常不再被主循环吞掉：
 *     单独捕获、计数、在悬浮窗显示，连续 5 次则停止并提示重开无障碍。
 *  M5 删除阴影/滚动条/图片相似度三种像素判定：
 *     README 自述阴影/滚动条识别率低；相似度在本环境因渲染延迟恒为 100%，
 *     只会造成误判底部。底部与翻页一律以页码节点为准。
 *  M6 主循环每个阶段打 [step] 日志，便于定位卡在哪一步。
 *  M7 翻页/末页判定改用阅读页右下角 "当前页/总页数" 无障碍文本节点：
 *     实测本环境（MuMu + Android15 转译）下 WebView 处理注入触摸极慢，
 *     单次滑动后 120 秒内截图都可能毫无变化；页码节点读取仅约 30ms
 *     且不受渲染延迟影响，是唯一可靠的进度与末页信号。
 *  M8 翻页改为「滑动 → 轮询页码 → 未生效再滑」：单次滑动常常数十秒不生效，
 *     盲滑会让阅读节奏与真实页码脱节；轮询到页码变化后才开始阅读倒计时。
 *     滑动后无障碍树会短暂回吐旧页码，故只认「前进跳变 + 二次确认」。
 *  M9 下滑幅度改为约 0.75 屏（从 85% 高度滑到 10% 高度）：
 *     好策按整屏翻页，原「行数 × H/24」只有约 1/3 屏，经常出现
 *     "有滑动动作但幅度不够、翻不过去"的半屏滑动。
 *     （M12 实测该方向本身无效，见下。）
 *  M10 页码基线改为连读三次取最后一次：循环开头常读到上一页的残留值，
 *     会把"残留值→当前值"误判成一次翻页，导致空转一整轮倒计时。
 *  M11 轮询窗口 8s → 20s：实测本环境 InputDispatcher 记录
 *     PandoraEntryActivity 单个 MotionEvent 处理耗时可达 2.5s，
 *     一次滑动产生的移动事件要数十秒才消费完，8s 窗口必然误判"未翻页"。
 *  M12 翻页方向改为横向左滑——这是本次真正的根因。实测在同一时刻：
 *     竖滑（0.75 屏、40 个采样点、400~700ms）无论用 adb 还是无障碍手势，
 *     页面像素 0 变化、页码不动；而横滑 800→200 立即 6→7、700→350
 *     立即 7→8、再滑 8→9。好策阅读器本身是横向翻页，"肌无力"正是
 *     手势方向不对/横移不足阈值时的半翻回弹。现改为从 90% 宽度滑到
 *     10% 宽度（约 0.8 屏），远超约 1/3 屏的翻页阈值。
 *  功能保留：速度选择、倒计时、悬浮窗拖动、章节切换。
 */

// M1: 限时等待无障碍服务
function waitA11y(timeoutMs) {
    var t0 = Date.now();
    while (!auto.service && Date.now() - t0 < timeoutMs) sleep(200);
    return !!auto.service;
}
if (!waitA11y(15000)) {
    toast("无障碍服务 15 秒内未就绪：请到 系统设置-无障碍 开启 Autox.js v7 后重跑");
    log("[step] 退出：无障碍服务未就绪");
    exit();
}
log("[step] 无障碍服务已连接");

// ==================== 全局配置参数 ====================

var screenWidth = device.width;
var screenHeight = device.height;

var swipeDuration = 500;
var chapterWaitTime = 3000;

var isRunning = false;
var bottomDetectCount = 0;
var maxBottomDetectCount = 3;
var a11yFailCount = 0;          // M4: 连续无障碍/手势失败计数
var lastPageCur = -1;           // M7: 上一轮读到的页码，用于判断本轮是否真的翻页
var maxA11yFailCount = 5;

var window = null;
var isMinimized = false;
var currentSpeedName = "normal";
var countdownThread = null;

var readingSpeed = {
    slow:   { minTime: 20000, maxTime: 30000 },
    normal: { minTime: 14000, maxTime: 22000 },
    fast:   { minTime: 8000,  maxTime: 14000 }
};

var currentSpeed = readingSpeed.normal;

// ==================== 初始化 ====================

toast("正在请求截图权限...");
log("[step] 请求截图权限");

// Android 14+ 每次运行都会弹系统授权页，需手动点「下一步/允许」
if (!requestScreenCapture()) {
    toast("截图权限请求失败：请在系统弹窗中点允许后重跑");
    log("[step] 退出：截图权限被拒绝");
    exit();
}
log("[step] 截图权限已获取");

toast("截图权限已获取，启动悬浮窗...");
createFloatyWindow();
log("[step] 悬浮窗已创建，等待点击开始");

// ==================== 工具函数 ====================

function random(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

// M2: 取独立快照；调用方负责 recycle 返回值
function snap() {
    return images.copy(captureScreen());
}

// M4: 手势前置检查；服务掉线时限时等重连，仍失败则抛带标记的异常
function ensureA11y() {
    if (auto.service) return;
    log("[step] 检测到无障碍服务掉线，等待重连(最多10秒)...");
    if (waitA11y(10000)) {
        log("[step] 无障碍服务已重连");
        return;
    }
    throw new Error("A11Y_DEAD");
}

// M4: 统一手势入口，返回失败原因而不是静默吞掉
function doGesture(duration, points) {
    ensureA11y();
    var ok = gesture.apply(null, [duration].concat(points));
    if (!ok) throw new Error("GESTURE_REJECTED");
}

function getRandomWaitTime() {
    var baseTime = random(currentSpeed.minTime, currentSpeed.maxTime);
    var variation = baseTime * (random(-20, 20) / 100);
    return Math.floor(baseTime + variation);
}

function getRandomSwipeDuration() {
    return random(400, 700);
}

function simulateReadingPause() {
    if (random(0, 100) < 15) {
        var pauseTime = random(3000, 8000);
        log("模拟阅读停顿: " + pauseTime + "ms");
        sleep(pauseTime);
    }
}

function startCountdown(seconds) {
    stopCountdown();
    countdownThread = threads.start(function() {
        var remainingSeconds = seconds;
        ui.run(function() {
            window.waitTimeText.setText("等待: " + remainingSeconds + "秒");
        });
        while (remainingSeconds > 0 && isRunning) {
            sleep(1000);
            remainingSeconds--;
            if (remainingSeconds > 0) {
                ui.run(function() {
                    window.waitTimeText.setText("等待: " + remainingSeconds + "秒");
                });
            } else if (remainingSeconds === 0) {
                ui.run(function() {
                    window.waitTimeText.setText("等待完成");
                });
            }
        }
    });
}

function stopCountdown() {
    if (countdownThread) {
        countdownThread.interrupt();
        countdownThread = null;
    }
}

// ==================== 悬浮窗控制 ====================

function createFloatyWindow() {
    window = floaty.window(
        <frame gravity="center">
            <vertical bg="#E0000000" padding="12" w="auto" h="auto">
                <text id="titleText" text="好策阅读" textColor="#FFFFFF" textSize="16sp" gravity="center" marginBottom="8"/>
                <text id="statusText" text="状态: 就绪" textColor="#AAAAAA" textSize="12sp" gravity="center" marginBottom="4"/>
                <text id="waitTimeText" text="等待: 0秒" textColor="#FFA500" textSize="11sp" gravity="center" marginBottom="4"/>
                <horizontal id="speedArea" gravity="center" marginBottom="8">
                    <text text="速度:" textColor="#FFFFFF" textSize="14sp" marginRight="8"/>
                    <button id="slowBtn" text="慢速" w="60" h="35" textSize="12sp" bg="#666666"/>
                    <button id="normalBtn" text="正常" w="60" h="35" textSize="12sp" bg="#2196F3"/>
                    <button id="fastBtn" text="快速" w="60" h="35" textSize="12sp" bg="#666666"/>
                </horizontal>
                <text id="ruleText" text="" textColor="#FFA500" textSize="11sp" gravity="center" marginBottom="8"/>
                <horizontal gravity="center">
                    <button id="actionBtn" text="开始" w="80" h="40" style="Widget.AppCompat.Button.Colored"/>
                    <button id="exitBtn" text="退出" w="80" h="40" marginLeft="8"/>
                </horizontal>
            </vertical>
        </frame>
    );

    // M3: 悬浮窗位置也按当前旋转帧计算，避免竖屏时飘出屏幕
    var probe = snap();
    var W = probe.getWidth(), H = probe.getHeight();
    probe.recycle();
    var windowWidth = 280;
    var windowHeight = 240;
    window.setPosition((W - windowWidth) / 2, (H - windowHeight) / 5);

    window.slowBtn.click(function() {
        currentSpeed = readingSpeed.slow;
        currentSpeedName = "slow";
        updateSpeedButtons();
        toast("已切换到慢速模式");
    });
    window.normalBtn.click(function() {
        currentSpeed = readingSpeed.normal;
        currentSpeedName = "normal";
        updateSpeedButtons();
        toast("已切换到正常模式");
    });
    window.fastBtn.click(function() {
        currentSpeed = readingSpeed.fast;
        currentSpeedName = "fast";
        updateSpeedButtons();
        toast("已切换到快速模式");
    });
    window.actionBtn.click(function() {
        if (isRunning) {
            stopReading();
        } else {
            startReading();
        }
    });
    window.exitBtn.click(function() {
        exit();
    });

    var isDragging = false;
    var startX, startY, windowX, windowY;
    window.titleText.setOnTouchListener(function(view, event) {
        switch (event.getAction()) {
            case event.ACTION_DOWN:
                isDragging = true;
                startX = event.getRawX();
                startY = event.getRawY();
                windowX = window.getX();
                windowY = window.getY();
                return true;
            case event.ACTION_MOVE:
                if (isDragging) {
                    window.setPosition(windowX + (event.getRawX() - startX), windowY + (event.getRawY() - startY));
                }
                return true;
            case event.ACTION_UP:
            case event.ACTION_CANCEL:
                isDragging = false;
                return true;
        }
        return false;
    });

    toast("悬浮窗已创建，拖动标题可移动位置");
}

function updateSpeedButtons() {
    ui.run(function() {
        window.slowBtn.setBackgroundColor(colors.parseColor("#666666"));
        window.normalBtn.setBackgroundColor(colors.parseColor("#666666"));
        window.fastBtn.setBackgroundColor(colors.parseColor("#666666"));
        switch (currentSpeedName) {
            case "slow":
                window.slowBtn.setBackgroundColor(colors.parseColor("#2196F3"));
                break;
            case "normal":
                window.normalBtn.setBackgroundColor(colors.parseColor("#2196F3"));
                break;
            case "fast":
                window.fastBtn.setBackgroundColor(colors.parseColor("#2196F3"));
                break;
        }
    });
}

function startReading() {
    isRunning = true;
    a11yFailCount = 0;
    window.actionBtn.setText("停止");
    ui.run(function() {
        window.speedArea.setVisibility(8);
        window.statusText.setText("状态: 运行中...");
        window.waitTimeText.setText("等待: 0秒");
        window.ruleText.setText("");
    });
    toast("开始自动阅读");
    threads.start(function() {
        mainLoop();
    });
}

function stopReading() {
    isRunning = false;
    window.actionBtn.setText("开始");
    stopCountdown();
    ui.run(function() {
        window.speedArea.setVisibility(0);
        window.statusText.setText("状态: 已停止");
        window.waitTimeText.setText("等待: 0秒");
    });
    toast("已停止阅读");
}

// ==================== 主循环 ====================

// M11/M12: 横滑实测数秒内生效，但偶发一次未过阈值；轮询 6s、最多 3 次即可。
var maxTurnAttempts = 3;
var turnPollMs = 6000;

function mainLoop() {
    while (isRunning) {
        try {
            log("[step] 1/4 读取屏幕尺寸与页码");
            var probe = snap();
            var W = probe.getWidth(), H = probe.getHeight();
            probe.recycle();
            log("[step] 当前旋转帧尺寸: " + W + "x" + H);

            var page0 = readStablePage();
            if (page0) {
                log("[step] 页码: " + page0.cur + "/" + page0.total);
            } else {
                log("[step] 未读到页码节点：无法判定翻页与末页，仅按固定节奏滑动");
            }

            if (page0 && page0.cur >= page0.total) {
                handleBottom(W, H);
            } else {
                bottomDetectCount = 0;
                log("[step] 2/4 左滑翻页并等待生效");
                turnPageWithRetry(W, H, page0);
            }

            var currentWaitTime = getRandomWaitTime();
            var waitSeconds = Math.floor(currentWaitTime / 1000);
            log("[step] 3/4 等待阅读 " + currentWaitTime + "ms");
            startCountdown(waitSeconds);
            sleep(currentWaitTime);
            stopCountdown();

            simulateReadingPause();
            ui.run(function() {
                window.statusText.setText("阅读中...");
                window.ruleText.setText("");
            });
            log("[step] 4/4 本轮结束");
        } catch (e) {
            // M4/M6: 不再静默吞掉；区分无障碍故障与其他错误
            var msg = (e && e.message) ? e.message : String(e);
            log("错误: " + e);
            if (msg === "A11Y_DEAD" || msg === "GESTURE_REJECTED") {
                a11yFailCount++;
                ui.run(function() {
                    window.statusText.setText("无障碍/手势异常 (" + a11yFailCount + "/" + maxA11yFailCount + ")");
                    window.ruleText.setText("本轮跳过，等待服务恢复");
                });
                if (a11yFailCount >= maxA11yFailCount) {
                    log("[step] 退出：无障碍服务连续不可用");
                    toast("无障碍服务持续不可用：请到 系统设置-无障碍 关闭再开启 Autox.js v7 后重跑");
                    stopReading();
                }
                sleep(2000);
            } else {
                ui.run(function() {
                    window.statusText.setText("错误: " + msg);
                });
                sleep(1000);
            }
        }
    }
}

function turnPageWithRetry(W, H, page0) {
    for (var attempt = 1; attempt <= maxTurnAttempts; attempt++) {
        performSwipeNextPage(W, H);
        a11yFailCount = 0;
        if (!page0) return;
        var t = Date.now();
        while (Date.now() - t < turnPollMs) {
            sleep(1500);
            var p = readPageIndicator();
            // 滑动后无障碍树会短暂回吐旧页码（实测 6→5→6），只认前进跳变并二次确认
            if (p && p.cur > page0.cur) {
                sleep(2000);
                var confirm = readPageIndicator();
                if (confirm && confirm.cur === p.cur) {
                    log("[step] 翻页生效: " + page0.cur + " -> " + p.cur + "（第" + attempt + "次滑动）");
                    lastPageCur = p.cur;
                    return;
                }
            }
        }
        log("[step] 第" + attempt + "次滑动后 " + turnPollMs + "ms 页码未变化");
        if (attempt < maxTurnAttempts) {
            var shown = attempt;
            ui.run(function() {
                window.statusText.setText("翻页中(尝试 " + shown + "/" + maxTurnAttempts + ")");
            });
        }
    }
    log("[step] 翻页超时：" + maxTurnAttempts + " 次滑动后页码仍未变化");
    ui.run(function() {
        window.statusText.setText("翻页超时，本轮跳过");
    });
}

function handleBottom(W, H) {
    bottomDetectCount++;
    ui.run(function() {
        window.statusText.setText("检测到底部 (" + bottomDetectCount + "/" + maxBottomDetectCount + ")");
        window.ruleText.setText("页码到达末页");
    });
    log("底部检测详情: 页码到达末页");

    if (bottomDetectCount >= maxBottomDetectCount) {
        toast("切换下一章");
        ui.run(function() {
            window.statusText.setText("切换章节...");
            window.ruleText.setText("");
        });
        log("[step] 左滑切换章节");
        performSwipeLeft(W, H);
        sleep(chapterWaitTime);
        bottomDetectCount = 0;
        lastPageCur = -1;
    }
}

// ==================== 滑动操作 ====================

// M12: 好策阅读页为横向翻页，竖滑无效。左滑下一页，幅度 0.8 屏。
function performSwipeNextPage(W, H) {
    var y = Math.floor(H * 0.5 + random(-30, 30));
    var startX = Math.floor(W * 0.90);
    var endX = Math.floor(W * 0.10);
    var duration = getRandomSwipeDuration();
    log("左滑翻页: x " + startX + " -> " + endX +
        "（约" + Math.floor((startX - endX) / W * 100) + "%屏）, y=" + y +
        ", 时长: " + duration + "ms, 旋转帧: " + W + "x" + H);
    var points = [];
    var steps = 10;
    for (var i = 0; i <= steps; i++) {
        var t = i / steps;
        points.push([Math.floor(startX + (endX - startX) * t), y + Math.floor(random(-3, 3))]);
    }
    doGesture(duration, points);
}

function performSwipeLeft(W, H) {
    var startX = W * 0.8;
    var endX = W * 0.2;
    var y = H * 0.5;
    var duration = random(500, 800);
    log("左滑切换章节: 从" + Math.floor(startX) + "到" + Math.floor(endX) + ", 时长: " + duration + "ms, 旋转帧: " + W + "x" + H);
    doGesture(duration, [[Math.floor(startX), Math.floor(y)], [Math.floor(endX), Math.floor(y)]]);
}

// ==================== 底部检测 ====================

// M7: 好策阅读页右下角有 "当前页/总页数" 文本节点，无障碍可直接读取（实测约30ms）。
// 本环境下 WebView 渲染/输入延迟可达数十秒，滑动后短时间内的截图不会变化，
// 因此截图相似度无法判断是否翻页；页码是唯一可靠的进度与末页信号。
function readPageIndicator() {
    var node = textMatches("\\d+\\s*/\\s*\\d+").findOne(1200);
    if (!node) return null;
    var m = /(\d+)\s*\/\s*(\d+)/.exec(node.text());
    if (!m) return null;
    return { cur: parseInt(m[1], 10), total: parseInt(m[2], 10) };
}

// M10: 连读三次取最后一次，规避无障碍树残留的上一页页码
function readStablePage() {
    var last = null;
    for (var i = 0; i < 3; i++) {
        var p = readPageIndicator();
        if (p) last = p;
        if (i < 2) sleep(1200);
    }
    return last;
}

// ==================== 事件处理 ====================

events.on("exit", function() {
    isRunning = false;
    if (window) window.close();
    toast("脚本已退出");
});

setInterval(function() {}, 1000);
