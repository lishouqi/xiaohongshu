import openai
from pprint import pprint

client = openai.OpenAI(api_key="sk-2keBL5LPe4DeEU3Lq1J50uAi5smlP2iKZoRV0XZ02R9vUJGK",
                       base_url="https://api.deerapi.com/v1"
                       )
pprint(
    [x.id for x in client.models.list()]
)

resp = client.chat.completions.create(
    model="claude-3-5-sonnet-20240620",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True
)

for chunk in resp:
    print(chunk.choices[0].delta.content, end="", flush=True)

