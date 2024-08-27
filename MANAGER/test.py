def gpt_generate(self, query):
    self.api_key = "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"
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