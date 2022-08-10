# 경도 위도 계산
def get_decimal_from_dms(dms, ref):
    degrees = dms[0]
    minutes = dms[1] / 60.0
    seconds = dms[2] / 3600.0

    if ref in ['S', 'W']:
        degrees = -degrees
        minutes = -minutes
        seconds = -seconds

    return round(degrees + minutes + seconds, 5)

def metadata_extract(image):
    # 메타 데이터 활용 부분
    import googlemaps
    import pandas as pd
    import urllib 
    import requests 
    import json 
    from PIL import Image
    from PIL.ExifTags import TAGS
    from math import dist
    from urllib.request import urlopen 
    from urllib.parse import urlencode, unquote, quote_plus

    # return 할 딕셔너리
    data = {}

    # 메타데이터 추출
    image_temp = image
    info = image_temp._getexif()
    image_temp.close()

    tagLabel = {}

    for tag, value in info.items():
        decoded = TAGS.get(tag, tag)
        tagLabel[decoded] = value

    # 메타데이터 GPS 데이터 추출
    exifGPS = tagLabel["GPSInfo"]
        
    # GPS 경도 위도 추출
    latData =  get_decimal_from_dms(exifGPS[2], exifGPS[1]) 
    longData = get_decimal_from_dms(exifGPS[4], exifGPS[3])

    #print("latData :", latData, ", longData :", longData)

    # GPS 데이터 (경도, 위도) -> 지도 상 위치
    gmaps = googlemaps.Client(key='AIzaSyAmh1pGPYPnSh2PWJ1P7X9mQTQO6Hvv8CM')
    reverse_geocode_result = gmaps.reverse_geocode((latData, longData),language='ko')

    address_components = reverse_geocode_result[0]['address_components']

    # 시
    for a in range(len(address_components)):
        if "administrative_area_level_1" in address_components[a]['types']:
            city = address_components[a]['long_name']
            #print("city :", city)

    # 구
    for a in range(len(address_components)):
        if "sublocality_level_1" in address_components[a]['types']:
            district = address_components[a]['long_name']
            #print("district : ", district)
            
    # 동
    for a in range(len(address_components)):
        if "sublocality_level_2" in address_components[a]['types']:
            dong = address_components[a]['long_name']
            #print("dong : ", dong)
            
    # 주변 랜드마크 출력
    city_dict = {"서울특별시" : "Seoul"} # 시 이름 한글 -> 영어 딕셔너리 추가 해야 함

    city_en = city_dict.get(city)

    # lat, lng 데이터 셋
    lat_lng_all= pd.read_csv('lat_lng_all.csv')

    # 특정 시, 구 데이터만 추출
    city_geo_data = lat_lng_all[lat_lng_all['location1'] == city]
    city_district_geo_data = city_geo_data[city_geo_data['location2'] == district]
    city_district_geo_data = city_district_geo_data[["name_kr", "lat", "lng"]]
    city_district_geo_data.set_index("name_kr")
    city_district_geo_data.to_dict('records')
    city_district_geo_data_dic = city_district_geo_data.set_index('name_kr').T.to_dict()

    # 현재 위치와 가까운 랜드마크 계산
    for key, value in city_district_geo_data_dic.items():
        lat = value["lat"]
        lng = value["lng"]
        
        a = (lat, lng)
        b = (latData, longData)
        
        city_district_geo_data_dic[key] = dist(a,b)
        
    geo_rank_list = sorted(city_district_geo_data_dic.items(), key=lambda x:x[1])
    geo_rank_top_list = geo_rank_list[:5]

    # 가까운 랜드마크 result_metadata에 저장
    for x in range(len(geo_rank_top_list)):
        #print(geo_rank_top_list[x][0])
        data["geo"+str(x)] = geo_rank_top_list[x][0]

    # 메타데이터 날짜 시간 추출
    image_DateTime = tagLabel['DateTime'] 

    tmp_DateTime = image_DateTime.split(" ")
    date = tmp_DateTime[0].split(":")
    year = date[0]
    month = date[1]
    day = date[2]
    time = tmp_DateTime[1].split(":")
    hour = time[0]
    minute = time[1]
    second = time[2]

    picture_date_ko = year + "년 " + month + "월 " + day + "일 " + hour + "시 " + minute + "분"
        
    # 촬영 날짜, 시간 data에 저장
    #print("촬영 날짜, 시간 : ", picture_date_ko)
    data["picture_date_ko"] = picture_date_ko

    hour = int(hour)

    # 시간대 
    if hour >= 7 and hour < 12:
        time_slot = "오전"
    elif hour >= 12 and hour < 14:
        time_slot = "점심"
    elif hour >= 14 and hour < 18:
        time_slot = "오후"
    elif hour >= 18 and hour < 20:
        time_slot = "저녁"
    elif hour >= 20 and hour < 24:
        time_slot = "밤"
    elif hour >= 0 and hour < 7:
        time_slot = "새벽"

    # 시간대 result_metadata에 저장
    #print("시간대 : ", time_slot)
    data["time_slot"] = time_slot

    # 휴일 여부
    year = year
    picture_date = int(year + month + day)

    holiday_key = 'oOnh7LyWyN8QvvHtkPh4PAIWpfLIA2x4bzWtFkclZ%2Bjyv5niovajPXw4nGeV%2F6xZSxwcyYnLRoIJ1odVXzdkqw%3D%3D'
    holiday_url = 'http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo?_type=json&numOfRows=50&solYear=' + str(year) + '&ServiceKey=' + str(holiday_key)

    holiday_req = urllib.request.Request(holiday_url)
    holiday_response_body = urlopen(holiday_req).read()
    holiday_data = json.loads(holiday_response_body) 
    holiday_res = pd.DataFrame(holiday_data['response']['body']['items']['item'])
    holiday_df = holiday_res[['dateName', 'locdate']]
    holiday_dict = holiday_df.set_index('locdate').T.to_dict('list')

    if picture_date in holiday_dict: 
        #print(holiday_dict[int(picture_date)][0])
        data["holiday"] = holiday_dict[int(picture_date)][0]
        
    # 날씨 -> 날짜, 시간, 주소 활용
    #picture_geo = city + district + dong

    def CheckStnIds(city, district):
        if city == "서울특별시": return 108
    
    weather_url = 'http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList'
    weather_enKey = 'oOnh7LyWyN8QvvHtkPh4PAIWpfLIA2x4bzWtFkclZ%2Bjyv5niovajPXw4nGeV%2F6xZSxwcyYnLRoIJ1odVXzdkqw%3D%3D'

    weather_startDt = year + month + day
    weather_startHh = hour
    weather_endDt = weather_startDt
    weather_endHh = weather_startHh
    weather_stnIds = CheckStnIds(city, district)

    params = f'?{quote_plus("ServiceKey")}={weather_enKey}&' + urlencode({ 
        quote_plus("pageNo"): "1",
        quote_plus("numOfRows"): "10", 
        quote_plus("dataType"): "JSON", 
        quote_plus("dataCd"): "ASOS",
        quote_plus("dateCd"): "HR",
        quote_plus("startDt"): weather_startDt, 
        quote_plus("startHh"): weather_startHh,
        quote_plus("endDt"): weather_endDt,
        quote_plus("endHh"): weather_endHh,
        quote_plus("stnIds"): weather_stnIds
        })

    weather_req = urllib.request.Request(weather_url + params)
    weather_response_body = urlopen(weather_req).read() 
    weather_data = json.loads(weather_response_body) 

    if weather_data:
        weather_res = pd.DataFrame(weather_data['response']['body']['items']['item'])

        # 시간, 지점 번호, 지점명, 기온, 강수량, 풍속, 풍향, 습도
        weather_result = weather_res[['tm','stnId','stnNm','ta','rn','ws','wd','hm',]]

        weather_result_dict = weather_result.to_dict('record')[0]

        # 기온
        weather_ta = float(weather_result_dict.get("ta"))
        if weather_ta <= 4:
            #print("#날씨짱추움")
            data["weather_ta"] = "#날씨짱추움"
        if weather_ta > 4 and weather_ta <= 11:
            #print("#날씨살짝추움")
            data["weather_ta"] = "#날씨살짝추움"
        if weather_ta > 11 and weather_ta <= 16:
            #print("#날씨시원함")
            data["weather_ta"] = "#날씨시원함"
        if weather_ta > 16 and weather_ta <= 21:
            #print("#날씨따뜻함")
            data["weather_ta"] = "#날씨따뜻함"
        if weather_ta > 21 and weather_ta <= 28:
            #print("#날씨살짝더움")
            data["weather_ta"] = "#날씨살짝더움"
        if weather_ta > 28:
            #print("#날씨짱더움")
            data["weather_ta"] = "#날씨짱더움"
            
        # 풍속    
        weather_ws = float(weather_result_dict.get("ws"))

        # 강수
        if weather_result_dict.get("rn"):
            weather_rn = float(weather_result_dict.get("rn"))
            if float(weather_rn) <= 2.5:
                #print("#비조금옴")
                data["weather_rain"] = "#비조금옴"
            if float(weather_rn) > 2.5 and float(weather_rn) <= 8.5:
                #print("#비옴")
                data["weather_rain"] = "#비옴"
            if float(weather_rn) > 8.5 and float(weather_rn) <= 20:
                #print("#비쏟아짐")
                data["weather_rain"] = "#비쏟아짐"
            if float(weather_rn) > 20:
                #print("#하늘에구멍")
                data["weather_rain"] = "#하늘에구멍"
        else:
            #print("#비안옴")
            data["weather_rain"] = "#비안옴"
    return data

def translate(caption_text):
    from googletrans import Translator
    translator = Translator()
    tr_results = translator.translate(caption_text, src='en', dest='ko')
    #print('Trans(EN):', tr_results.text, tr_results.src, tr_results.dest)
    return tr_results.text

def subject_extract(caption_text):
    import spacy

    # Load the language model
    nlp = spacy.load("en_core_web_sm")

    # nlp function returns an object with individual token information, 
    # linguistic features and relationships
    doc = nlp(caption_text)

    caption_list = []

    for token in doc:
        if str(token.dep_) == "ROOT":
            caption_sub = str(token.text)
        else:
            caption_list.append(token.text)

    caption_str = " ".join(caption_list[1:])

    # print(caption_sub, caption_str)
    return caption_sub, caption_str
