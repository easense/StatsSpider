import json

a = {'href': '15/07/150725.html', 'name': '陈巴尔虎旗', 'p_code': '150700000000', 'level': 3, 'code': '150725000000',
     'type': 'county'}

print(json.dumps(a, ensure_ascii=False))
# json.dump(a, ensure_ascii=False)
