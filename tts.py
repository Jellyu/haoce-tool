import asyncio, sys, re, os
import edge_tts

async def synth(text, out_mp3, voice='en-US-AriaNeural', rate='+0%', retries=3):
    for i in range(retries):
        try:
            c = edge_tts.Communicate(text, voice, rate=rate)
            await c.save(out_mp3)
            if os.path.getsize(out_mp3) > 1000:
                return True
        except Exception as e:
            print('tts retry', i, type(e).__name__, str(e)[:120])
            await asyncio.sleep(1.5)
    return False

if __name__ == '__main__':
    text = open(sys.argv[1], encoding='utf-8').read().strip()
    out = sys.argv[2]
    voice = sys.argv[3] if len(sys.argv) > 3 else 'en-US-AriaNeural'
    ok = asyncio.run(synth(text, out, voice))
    print('ok' if ok else 'FAIL', os.path.getsize(out) if os.path.exists(out) else 0)
    sys.exit(0 if ok else 1)
