import os

from openai import OpenAI


class ISICAISelector:

    def __init__(self):

        self.client = OpenAI(

            api_key=os.environ.get(
                "OPENAI_API_KEY"
            )

        )

    def choose_best(

        self,

        activity_name,

        candidates

    ):

        candidate_list = ""

        for i, candidate in enumerate(candidates, 1):

            candidate_list += (

                f"{i}. "

                f"{candidate['activity']}\n"

            )

        prompt = f"""

You are an ISIC classification expert.

Business Activity:

{activity_name}

Choose the SINGLE best matching ISIC activity from this list.

Candidates:

{candidate_list}

Return ONLY the activity name.

"""

        response = self.client.chat.completions.create(

            model="gpt-4.1-mini",

            messages=[

                {

                    "role": "user",

                    "content": prompt

                }

            ],

            temperature=0

        )

        return response.choices[0].message.content.strip()