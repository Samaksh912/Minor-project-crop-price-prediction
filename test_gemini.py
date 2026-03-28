import urllib.request
import json
import sys

data = json.dumps({
    'contents': [{'parts': [{'text': 'Return ONLY valid JSON, no markdown. 90-day daily price forecast for Apple in Tamil Nadu, India (Rs/Quintal). Schema: {"prices":[<90 floats>],"mae":<float>,"rmse":<float>,"mape_pct":<float 2-15>}'}]}],
    'generationConfig': {'maxOutputTokens': 400}
}).encode()

req = urllib.request.Request(
    'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key=AIzaSyB4PMYKxQIEYK2eapgTauAbI4WfYX_HEes',
    data=data,
    headers={'Content-Type': 'application/json'}
)

res = json.loads(urllib.request.urlopen(req).read())
finishReason = res['candidates'][0]['finishReason']
text = res['candidates'][0]['content']['parts'][0]['text']

print("Finish reason:", finishReason)
print("Text length:", len(text))
print("Data:", text)
