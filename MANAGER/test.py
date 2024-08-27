from openai import OpenAI
def gpt_generate(query):
    api_key = "***REMOVED***"
    client = OpenAI(api_key=api_key)
    model = "gpt-4"
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": query},
        ]
    )
    content = response.choices[0].message.content
    return content

print(gpt_generate("널 소개해봐"))