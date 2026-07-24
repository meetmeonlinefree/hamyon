import os
import json
import subprocess
import requests


PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")


PLAY_STORE_URL = (
    "https://play.google.com/store/apps/"
    "details?id=com.neuronit.hamyon"
)


def get_changed_files():
    """
    Получаем изменённые файлы
    """

    try:
        result = subprocess.check_output(
            [
                "git",
                "diff",
                "--name-only",
                "HEAD~1",
                "HEAD"
            ],
            text=True
        )

        return [
            file for file in result.strip().split("\n")
            if file
        ]

    except Exception:
        return []



def load_json(file_path):

    try:
        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception as e:

        print(
            "JSON error:",
            file_path,
            e
        )

        return None



def create_notification(files):

    title = None
    body = None
    notification_type = "content"
    url = ""


    for file in files:


        # ==========================
        # Обновление приложения
        # ==========================

        if file == "app_update.json":

            data = load_json(file)

            if data:

                version = data.get(
                    "version",
                    ""
                )

                title = data.get(
                    "title",
                    "📱 Новая версия приложения"
                )

                body = (
                    f"{data.get('message', '')} "
                    f"Версия {version}"
                )

                notification_type = "update"

                url = data.get(
                    "playStoreUrl",
                    PLAY_STORE_URL
                )

                break



        # ==========================
        # Новости приложения
        # ==========================

        elif file == "news.json":

            data = load_json(file)

            if data:


                title = data.get(
                    "title",
                    "📢 Новости"
                )


                body = data.get(
                    "message",
                    "Новые события в приложении"
                )


                notification_type = "news"


                url = data.get(
                    "url",
                    ""
                )


                break



    return (
        title,
        body,
        notification_type,
        url
    )



def send_push(
    title,
    body,
    notification_type,
    url
):


    endpoint = (
        f"https://fcm.googleapis.com/v1/projects/"
        f"{PROJECT_ID}/messages:send"
    )


    headers = {

        "Authorization":
            f"Bearer {ACCESS_TOKEN}",

        "Content-Type":
            "application/json"

    }



    data = {

        "type":
            notification_type

    }


    if url:

        data["url"] = url



    payload = {

        "message": {

            "topic":
                "hamyon_app",


            "notification": {

                "title":
                    title,

                "body":
                    body

            },


            "data":
                data,


            "android": {

                "priority":
                    "HIGH"

            }

        }

    }



    response = requests.post(
        endpoint,
        headers=headers,
        json=payload
    )


    print(
        response.text
    )




def main():

    print(
        "Checking changes..."
    )


    files = get_changed_files()


    print(
        "Changed files:",
        files
    )



    if not files:

        print(
            "No changes"
        )

        return



    (
        title,
        body,
        notification_type,
        url

    ) = create_notification(files)



    if not title:

        print(
            "No notification needed"
        )

        return



    print(
        title,
        body,
        notification_type,
        url
    )


    send_push(
        title,
        body,
        notification_type,
        url
    )



if __name__ == "__main__":

    main()
