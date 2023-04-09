from langdetect import DetectorFactory, detect ,detect_langs

def detect_language(text):
    try:
        print(detect_langs(text))
        return detect(text)
    except:
        return None
    
detect_language('陣型有點便秘怎麼辦')