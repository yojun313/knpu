def gpt_generate(self, query):
    self.api_key = "***REMOVED***"
    client = OpenAI(api_key=self.api_key)
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