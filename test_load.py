import urllib.request, json

communications = []
for i in range(1000):
    communications.append({
        'communication_id': f'123-{i}',
        'recipient': {'name': 'test', 'email': 'test@test.com', 'phone': ''},
        'message': 'test message'*10,
        'channel': 'whatsapp'
    })

data = json.dumps({'communications': communications, 'callback_url': 'http://example.com'})
print(f"Payload size: {len(data)} bytes")

req = urllib.request.Request(
    'https://xeno-channel-service-jimp.onrender.com/channel/send',
    data=data.encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    response = urllib.request.urlopen(req)
    print("Response Code:", response.getcode())
    print(response.read())
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code, e.read())
