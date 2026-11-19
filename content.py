import re, random
from textutil import word_count, detect_language

THEME_STEMS = [
    ('friendship', ['friendship', 'friend', 'companion', '友谊', '朋友']),
    ('loyalty', ['loyalty', 'loyal', '忠诚']),
    ('courage', ['courage', 'brave', 'bold', '勇气', '勇敢']),
    ('fear', ['fear', 'afraid', 'terror', '恐惧', '害怕']),
    ('loneliness', ['loneliness', 'lonely', 'alone', '孤独', '寂寞']),
    ('family', ['family', 'father', 'mother', '家庭', '父亲', '母亲']),
    ('belonging', ['belong', 'home', '归属', '家园']),
    ('power', ['power', 'control', 'authority', '权力', '控制']),
    ('equality', ['equality', 'equal', 'unequal', '平等']),
    ('freedom', ['freedom', 'free', 'liberty', '自由']),
    ('oppression', ['oppression', 'oppress', 'tyranny', '压迫', '暴政']),
    ('revolution', ['revolution', 'revolt', 'rebel', '革命', '反抗']),
    ('propaganda', ['propaganda', 'slogan', '宣传', '口号']),
    ('greed', ['greed', 'selfish', '贪婪', '自私']),
    ('corruption', ['corrupt', '腐败']),
    ('betrayal', ['betray', '背叛']),
    ('trust', ['trust', '信任']),
    ('community', ['community', 'collective', 'solidarity', '集体', '团结']),
    ('work', ['work', 'labour', 'labor', '劳动', '工作']),
    ('justice', ['justice', 'fairness', 'fair', '正义', '公平']),
    ('identity', ['identity', 'self', '身份', '自我']),
    ('memory', ['memory', 'remember', '记忆', '回忆']),
    ('loss', ['loss', 'lose', 'lost', '失去', '丧失']),
    ('grief', ['grief', 'mourning', '悲伤', '哀悼']),
    ('hope', ['hope', 'hopeful', '希望']),
    ('ambition', ['ambition', 'dream', '野心', '梦想']),
    ('guilt', ['guilt', 'guilty', '内疚', '愧疚']),
    ('shame', ['shame', 'ashamed', '羞耻']),
    ('truth', ['truth', 'honest', '真相', '诚实']),
    ('deception', ['deception', 'deceive', 'lie', '欺骗', '谎言']),
    ('kindness', ['kindness', 'kind', 'compassion', '善良', '同情']),
    ('cruelty', ['cruelty', 'cruel', '残酷']),
    ('survival', ['survival', 'survive', '生存', '幸存']),
    ('change', ['change', 'transform', '改变', '转变']),
    ('duty', ['duty', 'obligation', '责任', '义务']),
    ('sacrifice', ['sacrifice', '牺牲']),
    ('love', ['love', 'beloved', '爱', '爱情']),
    ('class', ['class', 'social', '阶级', '阶层']),
    ('education', ['education', 'school', 'teach', '教育', '学校']),
    ('science', ['science', 'scientific', 'experiment', '科学', '实验']),
    ('magic', ['magic', 'magical', 'spell', 'wizard', 'wand', '魔法', '巫师']),
    ('nature', ['nature', 'natural', '自然']),
    ('time', ['time', 'past', 'future', '时间', '过去', '未来']),
    ('mortality', ['death', 'die', 'dead', '死亡']),
]

THEME_ZH = {'friendship': '友谊', 'loyalty': '忠诚', 'courage': '勇气', 'fear': '恐惧',
            'loneliness': '孤独', 'family': '家庭', 'belonging': '归属', 'power': '权力',
            'equality': '平等', 'freedom': '自由', 'oppression': '压迫', 'revolution': '反抗',
            'propaganda': '宣传', 'greed': '贪婪', 'corruption': '腐败', 'betrayal': '背叛',
            'trust': '信任', 'community': '共同体', 'work': '劳动', 'justice': '正义', 'identity': '身份',
            'memory': '记忆', 'loss': '失去', 'grief': '悲伤', 'hope': '希望', 'ambition': '梦想',
            'guilt': '内疚', 'shame': '羞耻', 'truth': '真相', 'deception': '欺骗',
            'kindness': '善良', 'cruelty': '残酷', 'survival': '生存', 'change': '改变',
            'duty': '责任', 'sacrifice': '牺牲', 'love': '爱', 'class': '阶级',
            'education': '教育', 'science': '科学', 'magic': '魔法', 'nature': '自然', 'time': '时间',
            'mortality': '死亡'}

STOP_NAMES = {'The', 'This', 'That', 'These', 'Those', 'There', 'Then', 'They', 'Their', 'Them',
              'When', 'While', 'What', 'Why', 'How', 'Who', 'Which', 'Where', 'But', 'And', 'For',
              'She', 'Her', 'Him', 'His', 'Its', 'Our', 'Your', 'You', 'Not', 'Now', 'One', 'Two',
              'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Chapter', 'Part',
              'Book', 'Page', 'Mr', 'Mrs', 'Ms', 'Miss', 'Dr', 'Sir', 'Madam', 'Lord', 'Lady',
              'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
              'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
              'September', 'October', 'November', 'December', 'English', 'Chinese',
              'Others', 'Other', 'Someone', 'Somebody', 'Everyone', 'Everybody', 'Nobody',
              'Anyone', 'Anybody', 'Each', 'Both', 'All', 'Some', 'Many', 'Most', 'Few',
              'Several', 'People', 'Animals', 'Men', 'Women', 'Children', 'Comrades', 'Comrade'}

STOP_HEAD = {'and', 'but', 'so', 'because', 'if', 'when', 'as', 'then', 'that', 'which', 'while',
             'or', 'nor', 'yet', 'although', 'though', 'since', 'until', 'unless'}
STOP_TAIL = {'the', 'a', 'an', 'of', 'to', 'and', 'in', 'on', 'at', 'for', 'with', 'his', 'her',
             'their', 'was', 'were', 'is', 'had', 'he', 'she', 'it', 'they', 'as', 'by', 'from',
             'that', 'this', 'but', 'or', 'be', 'been', 'being', 'than', 'more', 'less', 'such',
             'very', 'much', 'too', 'also', 'just', 'only', 'even', 'still', 'yet', 'into', 'over',
             'under', 'between', 'through', 'about', 'like', 'when', 'where', 'who', 'which'}

INSIGHT_EN = [
    'The line {q} is more than a piece of description. It slows the scene down and lets us watch how {who} responds, so that {theme} stops being an abstract label and becomes something the reader can feel in the rhythm of the sentence.',
    'What stays with me about {q} is its restraint. Nothing is over-explained; the detail is simply placed where we cannot miss it. That confidence is what turns an ordinary observation about {theme} into a moment worth returning to.',
    'I read {q} as a small act of characterisation. The author gives us behaviour instead of explanation, and the hesitation inside the sentence tells us more about {who} than a direct description could. It is a quiet reminder that {theme} is usually revealed in passing.',
    '{q} looks simple, but the wording is carefully unbalanced. Something in it pulls against what the scene seems to say, and that tension is where the book\'s interest in {theme} begins to show.',
    'This passage earns its place because {q} connects the inner life of {who} to a concrete detail we can see. The image does not decorate the scene; it carries the emotional argument about {theme} without announcing itself.',
    'The pleasure of {q} is the way it trusts the reader. We are not told what to think about {who}; we are given a gesture, a pause, a choice of words, and left to assemble the meaning. That is how {theme} becomes part of the texture of the book rather than a message bolted on.',
    'I would underline {q} because it changes the temperature of the scene. The sentence could have been comic or merely informative, but it holds a note of unease, and that note colours the way we read everything that follows.',
    'There is an honesty in {q} that I admire. The book refuses to make {who} either a hero or a fool; the passage allows for contradiction, and that mixture is what makes its treatment of {theme} feel adult rather than sentimental.',
    'What {q} shows is how much can be carried by a small physical detail. A room, an object, a habit of speech: the text uses the visible world to make an invisible pressure felt, and {theme} becomes vivid because we can almost touch it.',
    'The sentence {q} has the quality of a hinge. It does not announce a turning point, yet after reading it we understand {who} differently. Good writing often works this way, adjusting our sympathy so gradually that we cannot say exactly when the change happened.',
    'I find {q} quietly unsettling, and that is a compliment. The sentence does not raise its voice, yet it keeps something back, and the reader senses the pressure underneath. Even when the book seems to be describing {who} from a safe distance, it leaves the door open for a much less comfortable judgement about {theme}.',
    '{q} is the kind of line that rewards a second reading. On the surface it belongs to the scene; underneath, it quietly prepares us for the question of {theme} that will matter later. The structure is doing work that the plot never has to explain.',
    'What I notice in {q} is the control of distance. The narration comes close enough for us to feel the discomfort of {who}, then steps back before the feeling becomes sentimental. That balance is difficult, and it is one reason the book can treat {theme} without preaching.',
    'This is a passage about status and pressure, although it never uses those words. {q} shows how small social signals can carry a whole hierarchy, and how {who} navigates it. The theme of {theme} emerges from those signals rather than from a speech.',
    'The detail in {q} feels observed rather than invented. That is a rare quality. It gives the scene a documentary texture and makes the larger question of {theme} land with more force, because we believe the world in which the question is asked.',
    'I like {q} for what it leaves out. The sentence stops before the obvious explanation, and the silence does the work. We are asked to notice {who}, to feel the gap between intention and effect, and to connect that gap to the book\'s ongoing concern with {theme}.',
    'Read aloud, {q} has a rhythm that slows the reader down. The pause is not decoration; it creates room for doubt. In that room, {theme} becomes a lived problem rather than a topic, and {who} becomes someone we recognise rather than merely observe.',
    'The passage works because {q} is specific. Instead of telling us that {who} is anxious or hopeful, it gives us a detail from the physical world. Specificity is what makes the emotional claim about {theme} credible, and it is why the scene survives beyond its plot function.',
    'What interests me in {q} is the gap between what is said and what is meant. The surface is calm, but the wording keeps slipping towards something else. That gap is where the book\'s irony lives, and it is also where its serious thinking about {theme} begins.',
    'This is one of those lines that seems merely to describe, yet quietly evaluates. {q} invites us to judge {who}, then makes judgement difficult by showing the pressure behind the behaviour. The result is a more humane, and more complicated, view of {theme}.',
]

INSIGHT_ZH = [
    '{q}这句看似只是叙述，实际上在悄悄调整读者的距离。它先让我们看见{who}的处境，再把“{theme}”变成可以感受的具体压力。作者没有直接下判断，而是把解释的空间留给读者，这种克制反而让文字更有分量。',
    '我读{q}时注意到一个细节：句子没有急着说明意义，而是让人物停在动作和沉默之间。正是这种停顿，让“{theme}”从抽象的词变成了具体的选择。好的叙述往往不解释，只把证据摆在我们面前。',
    '{q}在整段中像一个转折点，却并不张扬。它改变了我们对{who}的理解，也让“{theme}”这条线索慢慢浮出来。作者把判断藏在语气和细节里，读者要自己完成最后一步，这种参与感让句子更耐读。',
    '这段文字最打动我的是{q}里的分寸感。它没有把{who}写成单纯的好人或坏人，而是保留了矛盾：既想被理解，又害怕暴露。正因为有这种矛盾，“{theme}”才不是口号，而是人物必须面对的真实难题。',
    '{q}把看不见的情绪落在了一个看得见的细节上。房间、动作、一句没说完的话，都比直接抒情更有力量。作者用具体的生活质感托住了“{theme}”这个主题，所以读起来不空，也不需要额外解释。',
    '如果把{q}单独拿出来，它几乎普通得会被略过；放回段落里，它却在为后面的变化做准备。这样的句子像埋下的伏笔，既服务情节，也悄悄提出了关于“{theme}”的问题。重读时才会发现它的位置如此准确。',
    '我喜欢{q}里的克制。作者明明可以直接告诉我们{who}的感受，却选择用行为和语气暗示，让读者自己补全。正是这种留白，让“{theme}”有了回味的空间，也让人物显得真实而不是被作者操控。',
    '{q}让我想到，这本书并不急于给出答案。它让人物在具体处境里试探、犹豫、犯错，然后再让读者判断。这样的写法使“{theme}”不再是单一立场，而成为需要反复权衡的问题。',
    '从叙事节奏看，{q}放慢了这一段的速度。慢下来之后，{who}的迟疑和周围人的反应都变得清晰，主题“{theme}”也随之显出层次。很多有力的段落并不靠事件推动，而是靠这种短暂的停顿。',
    '{q}的妙处在于表面平静、内里紧张。句子没有直接冲突，却让人感到某种压力正在形成。作者把“{theme}”藏在这种压力里，等读者自己察觉，因此读到最后会比被直接告知更受触动。',
]

POST_TITLES_EN = [
    '{theme_title}: the quiet centre of {book}',
    'What {book} suggests about {theme}',
    'Reading {book} through the lens of {theme}',
    'The cost of {theme} in {book}',
    '{theme_title} and the ordinary choices in {book}',
    'Why {book} keeps returning to {theme}',
]

POST_BODIES_EN = [
    'One of the quiet arguments of {book} is that {theme} is tested in ordinary moments rather than dramatic ones. A conversation, a delay, a small decision can reveal more than a public confrontation. Reading the book this way makes its larger claims feel grounded, because the abstract question is always attached to a particular person in a particular room. That is also why the story stays with readers: the ideas arrive through experience, not through explanation.',
    '{book} treats {theme} as a problem rather than a slogan. Different characters carry different versions of it, and the text refuses to let any one of them be simply right. That disagreement is the most interesting thing about the book: it asks us to hold competing claims in mind and to notice what each person stands to lose.',
    'What I find most persuasive in {book} is the connection between {theme} and ordinary habit. The book is less interested in grand declarations than in the small routines that show what people value. Once you start looking for those routines, the story becomes a map of compromises, loyalties and quiet decisions, and the theme stops being an abstraction.',
    'A useful way to read {book} is to follow the question of {theme} across its scenes. Early on it appears as a personal difficulty; later it becomes a social one. The shift matters because it changes who is responsible and what a good answer would look like. The book does not resolve that tension neatly, and its honesty is the stronger for it.',
    'The most striking thing about {book} is how often it lets {theme} appear through what characters do not say. Silence, avoidance and small acts of kindness carry as much weight as argument. That technique makes the book rewarding to reread: the surface story remains clear, while the emotional and moral pattern underneath becomes richer.',
    'I keep returning to the way {book} stages {theme} through contrast. Two people respond to the same situation in incompatible ways, and the reader is left to weigh the costs. The book does not provide a verdict, but it teaches us to ask better questions about motive, circumstance and responsibility, which is more valuable than a tidy lesson.',
]

POST_TITLES_ZH = [
    '《{book}》中的{theme}',
    '从{theme}看《{book}》',
    '{book}：{theme}的代价',
    '《{book}》为什么反复写到{theme}',
    '{theme}与《{book}》里的日常选择',
]

POST_BODIES_ZH = [
    '《{book}》对“{theme}”的处理并不靠口号，而是把它放进日常选择里。一次沉默、一个迟到的决定、一句没有说完的话，都比直接说理更有力量。{author}让读者先看见具体的人，再意识到背后的处境，因此主题不是附加的说明，而是故事本身生长出来的问题。',
    '读《{book}》时，我越来越觉得“{theme}”不是一个可以用一句话回答的问题。不同人物给出不同答案，叙述者也不急着裁判谁对谁错。这样的写法把判断交还给读者，让人物保留复杂性，也让主题拥有了可以被反复讨论的空间。',
    '《{book}》最值得注意的地方，是它把“{theme}”落在具体的生活细节上。人物的习惯、语气和犹豫，往往比激烈的冲突更能说明问题。{author}没有把主题单独拎出来讲解，而是让它从场景里慢慢浮现，这种克制反而更有说服力。',
    '如果沿着“{theme}”这条线重读《{book}》，会发现它一开始像个人困境，后来逐渐变成人与人之间的结构性问题。这个变化很重要，因为它改变了责任的方向，也改变了“正确答案”的模样。作品没有给出廉价的和解，正是这一点让它显得诚实。',
    '我喜欢《{book}》处理“{theme}”的方式：它经常通过人物没有说出口的话来完成表达。沉默、回避、一个很小的善意，和争论一样有分量。这样的文本适合重读，因为表层故事很清楚，底下的情感和道德纹理却会随着阅读经验不断变厚。',
]

REPLY_EN = [
    'Your post about {title} made me look again at how {book} handles {theme}. What interests me is that the book rarely settles the question; it lets different characters embody different answers, and the reader has to weigh them. That openness is not vagueness. It is a way of making the theme belong to us rather than to a lesson.',
    'I agree with the main point in {title}, though I would push it a little further. The scenes that stay with me are the ones where {theme} appears indirectly, through habit or hesitation. When the book avoids naming the problem, it makes us more attentive to the pressure the characters are under.',
    'Thanks for raising {title}. It reminded me that {book} is careful about motive. Even the characters who behave badly are given a history, and that makes judgement harder. I think this is why the treatment of {theme} feels humane rather than moralistic.',
    'I see {title} slightly differently, but your reading made me reconsider. For me the key is the contrast between what people say and what they do. {book} keeps returning to that gap, and the gap is where the real thinking about {theme} happens.',
    'This is a thoughtful reading of {title}. I would add that the book often uses ordinary objects and routines to carry emotional weight. Those details make {theme} concrete, and they also make the world of the story believable enough for the larger questions to matter.',
    'Your point about {title} sent me back to a passage I had skimmed. What struck me this time was how much the book leaves unsaid. The silence around {theme} is not empty; it is full of social pressure and private doubt, and the reader has to infer both.',
    'I appreciate {title}, especially the attention to tone. {book} can be funny and uneasy at the same time, and that mixture keeps the reader off balance. The humour does not cancel the seriousness of {theme}; it makes the seriousness easier to approach.',
    'Reading {title}, I kept thinking about responsibility. {book} shows how quickly a small decision becomes a collective consequence, and how difficult it is to assign blame afterwards. That complexity is what makes its discussion of {theme} worth having.',
    'I would connect {title} to the question of belonging. So many of the conflicts in {book} come from people trying to find a place where they are recognised, and the search changes how they treat one another. Underneath the plot, {theme} is doing a lot of quiet work.',
    'This topic is worth discussing because {title} raises the question of how the book handles change. Nothing transforms overnight; the shift is cumulative, built out of repeated choices. That slow movement is one reason the ending feels earned rather than imposed.',
]

REPLY_ZH = [
    '你关于“{title}”的分析让我重新看了《{book}》处理“{theme}”的方式。作品很少直接给出结论，而是让不同人物带着各自的立场行动，读者必须自己权衡。这种开放不是含糊，而是把判断真正交还给我们。',
    '我同意“{title}”里的主要观点，但想再往前推一步。最打动我的往往不是冲突本身，而是人物在冲突前后的犹豫和沉默。作者不急着命名问题，反而让我们更清楚地感到“{theme}”带来的压力。',
    '谢谢你的“{title}”。它提醒我注意《{book}》对人物动机的耐心：即使做了错事的人，也有自己的来路和难处。正因为如此，作品对“{theme}”的处理才不显得说教，而是保留了理解的空间。',
    '我对“{title}”有一点不同看法，但你的分析让我重新考虑。对我来说，关键在人物说的话和做的事之间的缝隙。《{book}》反复回到这个缝隙，而关于“{theme}”的思考也正发生在那里。',
    '“{title}”这个角度很好。我想补充的是，作品常用日常物件和习惯来承载情绪，这些细节让“{theme}”变得具体，也让故事里的世界足够可信。只有世界可信，那些更大的问题才有分量。',
    '你的“{title}”让我回去重读了一段。这次我注意到作品留下了很多没有说出口的东西。围绕“{theme}”的沉默并不空，它装着社会压力和个人怀疑，读者要自己去补全。',
]

LEN_FILL_EN = [
    'The point matters because it shapes how we read the rest of the book, not just this single scene.',
    'What makes the passage durable is that it offers evidence rather than a verdict, leaving the reader with work to do.',
    'That small uncertainty is not a flaw; it is the source of the passage\'s continuing interest.',
]
LEN_FILL_ZH = [
    '这一点不仅影响我们对单个场景的理解，也改变了后面许多情节的分量。',
    '段落的力量来自它提供证据而不是结论，读者因此必须自己完成判断。',
    '这种没有被说满的余地不是缺陷，而正是它值得反复阅读的原因。',
]


def _stem_in(low, stem):
    if re.fullmatch(r'[a-z]+', stem):
        return re.search(r'\b' + re.escape(stem), low) is not None
    return stem in low


def get_themes(text):
    low = text.lower()
    found = []
    for name, stems in THEME_STEMS:
        if any(_stem_in(low, s) for s in stems):
            found.append(name)
    return found


def pick_theme(p, ctx):
    here = get_themes(p)
    if here:
        return random.choice(here)
    pool = ctx.get('themes') or ['change', 'hope', 'fear', 'belonging']
    return random.choice(pool)


SPEECH_VERBS = ('said', 'asked', 'replied', 'cried', 'shouted', 'whispered', 'muttered', 'answered',
                'explained', 'added', 'continued', 'called', 'remarked', 'suggested', 'announced',
                'declared', 'repeated', 'protested')


def collect_names(paragraphs, limit=12, title=''):
    skip = set(STOP_NAMES)
    skip.update(w for w in re.findall(r'[A-Za-z]{2,}', title or '') if w[0].isupper())
    speech = re.compile(r'\b([A-Z][a-z]{2,})\b(?=\s+(?:%s)\b)' % '|'.join(SPEECH_VERBS))
    possessive = re.compile(r"\b([A-Z][a-z]{2,})(?:'s|’s)\b")
    counts = {}
    for p in paragraphs[:1500]:
        for m in speech.finditer(p):
            w = m.group(1)
            if w not in skip:
                counts[w] = counts.get(w, 0) + 3
        for m in possessive.finditer(p):
            w = m.group(1)
            if w not in skip:
                counts[w] = counts.get(w, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    names = [w for w, n in ranked if n >= 2][:limit]
    return names if len(names) >= 2 else []


def collect_themes(paragraphs, limit=8):
    counts = {}
    for p in paragraphs[:1500]:
        low = p.lower()
        for name, stems in THEME_STEMS:
            if any(_stem_in(low, s) for s in stems):
                counts[name] = counts.get(name, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return [w for w, n in ranked][:limit]


def build_context(meta, paragraphs):
    lang = meta.get('language') or detect_language(' '.join(paragraphs[:30]))
    title = meta.get('short_title') or meta.get('title') or 'this book'
    minw = meta.get('min_words') or {}
    return {'book': title, 'title': title, 'author': (meta.get('author') or '').strip(),
            'lang': lang, 'names': collect_names(paragraphs, title=title) if lang == 'en' else [],
            'themes': collect_themes(paragraphs),
            'min_insight': int(minw.get('insight') or 25),
            'min_post': int(minw.get('topic') or minw.get('insight') or 25),
            'min_reply': int(minw.get('reply') or 25)}


def split_sentences(p, lang):
    if lang == 'zh':
        return [s.strip() for s in re.split(r'(?<=[。！？!?])', p) if s.strip()]
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', p) if s.strip()]


def _clauses(s, lang):
    if lang == 'zh':
        parts = re.split(r'(?<=[，；：,;])\s*', s)
    else:
        parts = re.split(r'(?<=[,;:])\s+', s)
    return [p.strip() for p in parts if p.strip()]


def _trim_fragment(s):
    s = s.strip(' “”"\'')
    s = re.sub(r'[,;:.\-—]+$', '', s).strip()
    ws = s.split()
    while ws and ws[0].lower() in STOP_HEAD:
        ws.pop(0)
    while ws and ws[-1].lower() in STOP_TAIL:
        ws.pop()
    return ' '.join(ws)


def pick_quote(p, lang):
    sents = split_sentences(p, lang)
    plain = [s for s in sents if not any(c in s for c in '“”"')]
    if lang == 'zh':
        base = plain or sents
        full = [s for s in base if 8 <= word_count(s) <= 45]
        clauses = [c for s in base for c in _clauses(s, lang) if 8 <= word_count(c) <= 32]
        pool = full or clauses or base or [p]
        s = random.choice(pool)
        if word_count(s) > 32:
            s = s[:32]
        return s.strip(' “”"\'')
    base = plain or sents
    full = [s for s in base if 5 <= word_count(s) <= 30]
    clauses = [c for s in base for c in _clauses(s, lang) if 5 <= word_count(c) <= 22
               and not any(ch in c for ch in '“”"')]
    if clauses and (not full or random.random() < 0.55):
        s = random.choice(clauses)
    elif full:
        s = random.choice(full)
    elif clauses:
        s = random.choice(clauses)
    else:
        s = random.choice(base or [p])
        words = s.split()
        s = ' '.join(words[:20])
    frag = _trim_fragment(s)
    return frag if len(frag) > 8 else random.choice(base or [p]).strip(' “”"\'')


def pick_who(p, ctx, quote=''):
    if ctx.get('lang') == 'zh':
        return '文中的人物' if random.random() < 0.7 else '主人公'
    names = ctx.get('names') or []
    for source in (quote, p):
        present = [n for n in names if re.search(r'\b%s\b' % re.escape(n), source)]
        if present:
            return random.choice(present)
    return random.choice(['the central figure', 'the people in this passage', 'the narrator'])


def ensure_len(text, minw, lang, tries=3):
    fills = LEN_FILL_ZH if lang == 'zh' else LEN_FILL_EN
    sep = '' if lang == 'zh' else ' '
    for i in range(tries):
        if word_count(text) >= minw:
            break
        text = text + sep + fills[i % len(fills)]
    return text


def make_insight(p, used, ctx):
    lang = ctx.get('lang', 'en')
    raw_q = pick_quote(p, lang)
    theme = pick_theme(raw_q if get_themes(raw_q) else p, ctx)
    if lang == 'zh':
        theme = THEME_ZH.get(theme, theme)
        q = '“%s”' % raw_q.strip('“”" ').replace('“', '').replace('”', '')
    else:
        q = '"%s"' % raw_q.replace('"', "'")
    ctx = dict(ctx, q=q, who=pick_who(p, ctx, raw_q), theme=theme)
    pool = INSIGHT_ZH if lang == 'zh' else INSIGHT_EN
    for _ in range(30):
        t = random.choice(pool)
        if t in used:
            continue
        s = t.format(**ctx)
        if word_count(s) >= ctx['min_insight']:
            used.add(t)
            return s
    if lang == 'zh':
        s = '%s这一段值得细读。它没有直接说明“%s”，而是通过具体的动作和语气让读者自己体会。%s' % (
            q, theme, LEN_FILL_ZH[0])
    else:
        s = ('The line %s deserves a second reading. It does not explain %s directly, but lets a concrete detail '
             'carry the emotional weight of the scene. %s' % (q, theme, LEN_FILL_EN[0]))
    return ensure_len(s, ctx['min_insight'], lang)


def make_posts(ctx, n, used):
    lang = ctx.get('lang', 'en')
    titles = POST_TITLES_ZH if lang == 'zh' else POST_TITLES_EN
    bodies = POST_BODIES_ZH if lang == 'zh' else POST_BODIES_EN
    themes = ctx.get('themes') or ['change', 'hope']
    combos = [(t, b, th) for t in titles for b in bodies for th in themes]
    random.shuffle(combos)
    out, seen = [], set()
    for tpl_t, tpl_b, theme in combos:
        tname = THEME_ZH.get(theme, theme) if lang == 'zh' else theme
        title = tpl_t.format(book=ctx['book'], theme=tname, theme_title=tname.title())
        if title in used or title in seen:
            continue
        body = tpl_b.format(book=ctx['book'], theme=tname, author=ctx.get('author') or ('作者' if lang == 'zh' else 'the author'))
        body = ensure_len(body, ctx['min_post'], lang)
        seen.add(title)
        out.append((title, body))
        if len(out) >= n:
            return out
    return out


def make_reply(title, i, ctx):
    lang = ctx.get('lang', 'en')
    theme = random.choice(ctx.get('themes') or ['change', 'hope'])
    if lang == 'zh':
        theme = THEME_ZH.get(theme, theme)
    title = re.sub(r'\s+', ' ', str(title or '')).strip().strip('"“”')[:100] or ('这本书' if lang == 'zh' else 'this topic')
    ctx = dict(ctx, title=title, theme=theme)
    if lang == 'zh':
        text = REPLY_ZH[i % len(REPLY_ZH)].format(**ctx)
    else:
        text = REPLY_EN[i % len(REPLY_EN)].format(**ctx)
    return ensure_len(text, ctx['min_reply'], lang)
