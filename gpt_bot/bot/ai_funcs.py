from configGPT import AI_TOKEN
from openai import OpenAI

def askAi_func(question, context = 'you are a buisness assistant'):
    print('started')
    
    client = OpenAI(
        api_key=AI_TOKEN
    )

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": context},
            {
                "role": "user",
                "content": question
            }
        ]
    )
    print('ended')
    return completion.choices[0].message.content