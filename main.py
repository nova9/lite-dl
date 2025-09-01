# Built in modules
import sys
import re
import os
from alive_progress import alive_bar

# Third party modules
import requests

print("\n\n\n\n\n\n\n\n\n\n\n\n")
os.system("clear")


def init_link_to_link_base(init_link):
    link_base = re.search(r"\/\w\/(.+)", init_link).group(1)  # first match - first paranthesis
    return link_base


def link_base_to_link(link_base, page_number):
    return f'https://literotica.com/api/3/stories/{link_base}?params=%7B"contentPage"%3A{page_number}%7D'


def get_json(link: str) -> dict:
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:53.0) Gecko/20100101 Firefox/53.0"
    }
    response = requests.get(link, headers=headers)
    # print(response.status_code)
    # print(response.encoding)

    json_dict = response.json()
    return json_dict


def get_story(link_base):
    init_json = get_json(link_base_to_link(link_base, 1))
    number_of_pages = init_json["meta"]["pages_count"]
    title = init_json["submission"]["title"]
    author_name = init_json["submission"]["authorname"]
    author_homepage = init_json["submission"]["author"]["homepage"]
    story_link = f"https://literotica.com/s/{link_base}"

    title_with_border = f"""
--------------------------------------------
|Title: {title}|
|Author: {author_name}|
|Author Homepage: {author_homepage}|
|Story link: {story_link}|
--------------------------------------------"""
    print(title_with_border)
    with open("story.txt", mode="a") as text_file:
        text_file.write(title_with_border)

    with alive_bar(number_of_pages) as bar:
        for i in range(1, number_of_pages + 1):
            page_number_with_border = f"""
--------------------------------------------
|PAGE {i}|
--------------------------------------------\n"""
            # print(page_number_with_border)

            story = get_json(link_base_to_link(link_base, i))["pageText"]
            # print(story)
            with open("story.txt", mode="a") as text_file:
                text_file.write(page_number_with_border)
                text_file.write(story)
            bar()


def get_series(link_base):
    init_json = get_json(link_base_to_link(link_base, 1))


    series = init_json["submission"]["series"]  # list

    print(series)

    if series == []:
        get_story(link_base)
    else:
        for i in series['items']:
            get_story(i["url"])


if __name__ == "__main__":
    # x='https://www.literotica.com/s/life-after-the-lottery-ch-11?page=2'
    if os.path.isfile("story.txt"):
        print("There is a story in the directory. Delete it")
    else:
        print(sys.argv[1])
        link_base = init_link_to_link_base(sys.argv[1])
        print(link_base)
        get_series(link_base)

    print(
        "\n\n\n\n|||||||Create a github issue if you encouter any problem|||||||".upper()
    )
