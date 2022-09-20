import spacy
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
from datetime import datetime
from googletrans import Translator

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

def CheckStnIds(city):
    if city == "서울특별시": return 108
    if city == "부산광역시": return 159
    if district == "여수시": return 168
    if district == "강릉시": return 105

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

# 메타데이터 GPS 데이터 추출
def gps_extract(image):
    image_temp = image
    info = image_temp._getexif()
    image_temp.close()

    tagLabel = {}
    
    for tag, value in info.items():
        decoded = TAGS.get(tag, tag)
        tagLabel[decoded] = value

    if "GPSInfo" in tagLabel:
        exifGPS = tagLabel["GPSInfo"]
        latData =  get_decimal_from_dms(exifGPS[2], exifGPS[1]) 
        longData = get_decimal_from_dms(exifGPS[4], exifGPS[3])
    
    return latData, longData

# 메타데이터 날짜 시간 추출
def date_extract(image):
    image_temp = image
    info = image_temp._getexif()
    image_temp.close()

    tagLabel = {}
    
    for tag, value in info.items():
        decoded = TAGS.get(tag, tag)
        tagLabel[decoded] = value

    if "DateTime" in tagLabel:
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
    
    return year, month, day, hour, minute, second

def gps_landmark(latData, longData):
    gmaps = googlemaps.Client(key='AIzaSyBePXHXaSiJp9y4jokaZn5jo_azxF_XfO4')
    reverse_geocode_result = gmaps.reverse_geocode((latData, longData),language='ko')

    address_components = reverse_geocode_result[0]['address_components']
    
    global city, district, dong

    # 시
    for a in range(len(address_components)):
        if "administrative_area_level_1" in address_components[a]['types']:
            city = address_components[a]['long_name']
            print("city : ", city)

    # 구
    for a in range(len(address_components)):
        if "sublocality_level_1" in address_components[a]['types'] or "locality" in address_components[a]['types']:
            district = address_components[a]['long_name']
            print("district : ", district)

    # 동
    for a in range(len(address_components)):
        if "sublocality_level_2" in address_components[a]['types']:
            dong = address_components[a]['long_name']
            print("dong : ", dong)

    # lat, lng 데이터 셋
    lat_lng_all= pd.read_csv('lat_lng_all.csv')

    # 특정 시, 구 데이터만 추출
    city_geo_data = lat_lng_all[lat_lng_all['location1'] == city]

    if "sublocality_level_1" in address_components[a]['types']:
        city_district_geo_data = city_geo_data[city_geo_data['location2'] == district]
    else: city_district_geo_data = city_geo_data
    
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
    
    return city, district, geo_rank_top_list

# 날짜 -> 시간대
def date_timeslot(year, month, day, hour, minute):
    picture_date_ko = year + "년_" + month + "월_" + day + "일_" + hour + "시_" + minute + "분"
    
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

    return picture_date_ko, time_slot

    # 날짜 -> 휴일
def date_holiday(year, month, day):
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
        return holiday_dict[int(picture_date)][0]

# 날씨 -> 날짜, 시간, 주소 활용
def gps_date_weather(year, month, day, hour, city):
    weather_url = 'http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList'
    weather_enKey = 'oOnh7LyWyN8QvvHtkPh4PAIWpfLIA2x4bzWtFkclZ%2Bjyv5niovajPXw4nGeV%2F6xZSxwcyYnLRoIJ1odVXzdkqw%3D%3D'
    weather_startDt = year + month + day
    weather_startHh = hour
    weather_endDt = weather_startDt
    weather_endHh = weather_startHh
    weather_stnIds = CheckStnIds(city)

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
    
    if not (datetime.today().year == int(year) and datetime.today().month == int(month) and datetime.today().day == int(day)):
        print(weather_data['response']['header']['resultMsg'])
        if not "ERROR" in str(weather_data['response']['header']['resultMsg']):

            weather_res = pd.DataFrame(weather_data['response']['body']['items']['item'])

            # 시간, 지점 번호, 지점명, 기온, 강수량, 풍속, 풍향, 습도
            weather_result = weather_res[['tm','stnId','stnNm','ta','rn','ws','wd','hm',]]

            weather_result_dict = weather_result.to_dict('record')[0]

            # 기온
            weather_ta = float(weather_result_dict.get("ta"))
            if weather_ta <= 4:
                weather_ta_ko = "#날씨짱추움"
            if weather_ta > 4 and weather_ta <= 11:
                weather_ta_ko = "#날씨살짝추움"
            if weather_ta > 11 and weather_ta <= 16:
                weather_ta_ko = "#날씨시원함"
            if weather_ta > 16 and weather_ta <= 21:
                weather_ta_ko = "#날씨따뜻함"
            if weather_ta > 21 and weather_ta <= 28:
                weather_ta_ko = "#날씨살짝더움"
            if weather_ta > 28:
                weather_ta_ko = "#날씨짱더움"

            # 풍속    
            weather_ws = float(weather_result_dict.get("ws"))

            # 강수
            if weather_result_dict.get("rn"):
                weather_rn = float(weather_result_dict.get("rn"))
                if float(weather_rn) <= 2.5:
                    weather_rain = "#비조금옴"
                if float(weather_rn) > 2.5 and float(weather_rn) <= 8.5:
                    weather_rain = "#비옴"
                if float(weather_rn) > 8.5 and float(weather_rn) <= 20:
                    weather_rain = "#비쏟아짐"
                if float(weather_rn) > 20:
                    weather_rain = "#하늘에구멍"
            else:
                weather_rain = "#비안옴"

        return weather_ta_ko, weather_rain

    return None, None

def metadata_extract(image):
    latData, longData = gps_extract(image)
    year, month, day, hour, minute, second = date_extract(image)
    

    if latData and longData:
        city, district, geo_rank_top_list = gps_landmark(latData, longData)
    else:
        city, district, geo_rank_top_list = None, None, None

    
    if year and month and day and hour and minute and second:
        picture_date_ko, time_slot = date_timeslot(year, month, day, hour, minute)
        holiday = date_holiday(year, month, day)
    else:
        picture_date_ko, time_slot, holiday = None, None, None
        
    if latData and longData and year and month and day and hour and minute and second:
        weather_ta_ko, weather_rain = gps_date_weather(year, month, day, hour, city)
    else:
        weather_ta_ko, weather_rain = None, None

    result_metadata = {}

    if geo_rank_top_list:
        for x in range(len(geo_rank_top_list)):
            result_metadata["geo"+str(x)] = geo_rank_top_list[x][0]

    if picture_date_ko:
        result_metadata["picture_date_ko"] = "#" + picture_date_ko

    if time_slot:
        result_metadata["time_slot"] = "#" + time_slot

    if holiday:
        result_metadata["holiday"] = "#" + holiday

    if weather_ta_ko: 
        result_metadata["weather_ta"] = weather_ta_ko

    if weather_rain:
        result_metadata["weather_rain"] = weather_rain    

    return result_metadata