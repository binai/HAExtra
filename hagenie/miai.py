#!/usr/bin/env python
# coding: utf-8

import os, sys, json
try:
    from urllib2 import urlopen
    from urllib import unquote
    reload(sys)
    sys.setdefaultencoding('utf8')
except ImportError:
    from urllib.request import urlopen
    from urllib.parse import unquote

#
def log(message):
    sys.stderr.write(message + '\n')

# Log HTTP payload
REQUEST_METHOD = os.getenv('REQUEST_METHOD')
if REQUEST_METHOD:
    log(REQUEST_METHOD + ' ' + os.environ['SCRIPT_NAME'] + '?' + os.environ['QUERY_STRING'] + '\n')

#
_appName = None
_haUrl = None
def validateToken(queryString):
    parts = queryString.split('_')
    if len(parts) > 3 and (parts[1] == 'http' or parts[1] == 'https'):
        global _appName
        global _haUrl
        _appName = unquote(parts[0])
        _haUrl = parts[1] + '://' + parts[2] + ':' + parts[3] + '/api/%s'
        if len(parts) > 4:
            _haUrl += '?api_password=' + parts[3]
        log('validateToken: ' + _appName + ', HAURL: ' + _haUrl)
        return True
    return False

#
def haCall(cmd, data=None):
    url = _haUrl % cmd
    method = 'POST' if data else 'GET'
    log('HA ' + method + ' ' + url)
    if data:
        log(data)
    if url.startswith('https'): # We need extra requests lib for HTTPS POST
        import requests
        result = requests.request(method, url, data=data, timeout=3).text
    else:
        result = urlopen(url, data=data, timeout=3).read()

    #log('HA RESPONSE: ' + result)
    return json.loads(result)

#
STATE_NAMES = {
    'on': '开启状态',
    'off': '关闭状态',

    'home': '在家',
    'not_home': '离家',

    'cool': '制冷模式',
    'heat': '制热模式',
    'auto': '自动模式',
    'dry': '除湿模式',
    'fan': '送风模式',

    'open': '打开状态',
    'opening': '正在打开',
    'closed': '闭合状态',
    'closing': '正在闭合',

    'unavailable': '不可用',
}

#
def handleState(state):
    return '为' + STATE_NAMES[state] if state in STATE_NAMES else state

#
def handleEntity(entity_id, item, query):
    domain = entity_id[:entity_id.find('.')]
    state = item['state']
    if domain == 'sensor' and domain == 'binary_sensor' and domain == 'device_tracker':
        return handleState(state)

    if query.startswith('打开') or query.startswith('开'):
        action = '打开'
        service = 'open_cover' if domain == 'cover' else 'turn_on'
    elif query.startswith('关'):
        action = '关闭'
        service = 'close_cover' if domain == 'cover' else 'turn_off'
    else:
        return handleState(state)

    data = '{"entity_id":"' + entity_id + '"}'
    result = haCall('services/' + domain + '/' + service, data)
    return action + "成功" if type(result) is list else "不成功"

#
def handleQuery(query, request_type):
    items = haCall('states')
    for item in items:
        entity_id = item['entity_id']
        if entity_id.startswith('group') and not entity_id.startswith('group.all_'):
            continue

        attributes = item['attributes']
        friendly_name = attributes.get('friendly_name')
        if friendly_name is not None and query.endswith(friendly_name):
            return (True, friendly_name + handleEntity(entity_id, item, query.split(_appName)[-1]))

    return (False, "您好主人，我能为你做什么呢？" if request_type == 0 else _appName + "未找到设备，请再说一遍吧")

#
def handleRequest(body):
    if not validateToken(os.environ['QUERY_STRING']):
        return (True, "需要配置服务端口类型哦")

    request = body['request']

    #
    if 'no_response' in request:
        return (False, '主人，您还在吗？')

    #
    query = body['query']
    request_type = request['type']
    if request_type == 2:
        return (True, "再见主人，" + _appName + "在这里等你哦！")

    return handleQuery(query, request_type)

# Main process
try:
    if REQUEST_METHOD == 'POST':
        body = json.load(sys.stdin)
        log(json.dumps(body, indent=2, ensure_ascii=False))
    else:
        # TEST only
        body = {
        }
    is_session_end, text = handleRequest(body)
except:
    import traceback
    log(traceback.format_exc())
    is_session_end, text = (True, "主人，程序出错啦！")

#
response = {
    'version': '1.0',
    'is_session_end': is_session_end,
    'response': {
        'open_mic': not is_session_end,
        'to_speak': {'type': 0,'text': text},
        #'to_display': {'type': 0,'text': text}
     },
}

# Process final result
result = json.dumps(response, indent=2, ensure_ascii=False)
if REQUEST_METHOD:
    log('RESPONSE ' + result)

    print('Content-Type: application/json\r\n')
    print(result)
