import json
from typing import List
from datetime import datetime
from tweepy import API, Cursor, OAuthHandler, TweepError
from python_utils import get_environment_variable
from config import DEFAULT_TWITTER_USER_ID, OUTPUT_FOLDER_PATH, FILENAME_SEPARATOR


class TwitterClient:
    def __init__(self, user=DEFAULT_TWITTER_USER_ID, debug=True):
        self.user = user
        self.consumer_key = get_environment_variable("TWITTER_CONSUMER_KEY")
        self.consumer_secret = get_environment_variable("TWITTER_CONSUMER_SECRET")
        self.access_token = get_environment_variable("TWITTER_ACCESS_TOKEN")
        self.access_token_secret = get_environment_variable("TWITTER_ACCESS_TOKEN_SECRET")
        self.twitter_client = self.get_authenticated_client()
        self.debug = debug

        self.streams = []

        if self.user:
            self.user = self.twitter_client.get_user(self.user)

    # TODO: add context managers
    # def __enter__(self):
    #     pass
    #
    # def __exit__(self, exception_type, exception_value, exception_traceback):
    #     if exception_type:
    #         print(f"{exception_type} while closing TwitterClient: {exception_value}")

    def get_authenticated_client(self):
        auth = OAuthHandler(self.consumer_key, self.consumer_secret)
        auth.set_access_token(self.access_token, self.access_token_secret)
        return API(auth)

    def add_stream(self):
        self.streams.append("stream")

    # TODO: make cached version combined with storage
    def get_names_from_ids(self, user_ids):
        user_names = []
        for user_id in user_ids:
            try:
                user = self.twitter_client.get_user(user_id)
                user_names.append(user.name)
            except TweepError as e:
                if self.debug:
                    print(f"Failed to get user info for {user_id}: {e}")
                user_names.append(f"{user_id} (unavailable/deactivated)")
        return user_names

    def get_ids_from_names(self, user_names):
        user_ids = []
        for user_name in user_names:
            try:
                print(f"getting data for {user_name}")
                # TODO: explicit id/name
                user = self.twitter_client.get_user(user_name)
                user_ids.append(user.id)
            except TweepError as e:
                if self.debug:
                    print(f"Failed to get user info for {user_name}: {e}")
                user_names.append(f"{user_name} (unavailable/deactivated)")
        return user_ids

    def get_user_timeline(self, user_id, count=20, since_id=None):  # todo: include RT
        res = Cursor(self.twitter_client.user_timeline, id=user_id, since_id=since_id).items(count)
        return res

    def get_user_profiles(self, user_identifiers: List[str]):
        user_profiles = [self.get_user_profile(user_identifier) for user_identifier in user_identifiers]
        return user_profiles

    def get_user_profile(self, user_identifier):
        try:
            if self.debug:
                print(f"getting data for user {user_identifier}")
            user_profile = self.twitter_client.get_user(user_identifier)
            return user_profile
        except TweepError as err:
            if self.debug:
                print(f"failed to get info for user {user_identifier}: {err}")

    def get_followers_ids(self, user_id=None):
        if not user_id:
            user_id = self.user.id

        followers_ids = []
        for friend in Cursor(self.twitter_client.followers_ids, id=user_id).items():
            followers_ids.append(friend)

        followers_ids.sort()
        return followers_ids

    def compare_followers_ids(self):
        output_file_name = f"{self.user.id}" \
                           f"{FILENAME_SEPARATOR}" \
                           f"{str(self.user.name).replace(' ', '_')}" \
                           f"{FILENAME_SEPARATOR}" \
                           f"followers_ids.json"

        output_path = OUTPUT_FOLDER_PATH / output_file_name

        # get follower status from api
        followers_ids_from_client = self.get_followers_ids()
        followers_ids_dict = {"user_id": self.user.id,
                              "user_name": self.user.name,
                              "date": str(datetime.now()),
                              "timestamp": str(datetime.timestamp(datetime.now())),
                              "followers_count": len(followers_ids_from_client),
                              "followers_ids": followers_ids_from_client}

        # get most recently saved follower status if available
        if output_path.exists():
            with output_path.open(mode='r') as output:
                followers_ids_history = output.readlines()
                most_recent_followers_ids = json.loads(followers_ids_history[len(followers_ids_history) - 1])
            followers_ids_from_file = most_recent_followers_ids["followers_ids"]

            # calculate differences
            followers_ids_from_file_set = set(followers_ids_from_file)
            followers_ids_from_client_set = set(followers_ids_from_client)

            unfollowers = followers_ids_from_file_set - followers_ids_from_client_set
            new_followers = followers_ids_from_client_set - followers_ids_from_file_set
        else:
            unfollowers = set()
            new_followers = set(followers_ids_from_client)

        # update db
        with output_path.open(mode="a+") as output:
            print(json.dumps(followers_ids_dict), file=output)

        return unfollowers, new_followers, len(followers_ids_from_client)
