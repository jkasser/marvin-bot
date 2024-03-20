import os.path
from pymongo import MongoClient
from bson.objectid import ObjectId
import yaml
import datetime


class MarvinDB:

    def __init__(self):
        path = os.path.dirname(os.path.abspath(os.path.dirname(__file__))) + '\\config.yaml'
        with open(path, "r") as file:
            cfg = yaml.safe_load(file)
        username = cfg["database"]["username"]
        password = cfg["database"]["password"]
        self.database_name = cfg["database"]["name"]
        self.mongo = MongoClient(
            f"mongodb+srv://{username}:{password}@{self.database_name}.akjlnty.mongodb.net/",
            tlsAllowInvalidCertificates=True
        ).marvindb

    def select_collection(self, table_name):
        if table_name not in self.mongo.list_collection_names():
            self.mongo.create_collection(table_name)
        return self.mongo[table_name]

    def get_user_record(self, user_id):
        db = self.select_collection('users')
        user_record = db.find_one(
            {
                '_id': ObjectId(user_id)
            }
        )
        # self.close_conn()
        for key, value in user_record.items():
            if isinstance(value, ObjectId):
                user_record[key] = str(user_record[key])
            if isinstance(value, datetime.datetime):
                user_record[key] = str(datetime.datetime.now())
        return user_record

    def run_find_one_query(self, table, query_to_run):
        for key, value in query_to_run.items():
            if '$' in key:  # this means we are doing an and or or, which means a list of dictionaries
                for subdict in value:  # for each sub dictionary in the list
                    for subkey, subvalue in subdict.items():  # iterate through each dict and update
                        if "_id" == subkey:
                            # print('this is an _id, wrap it in an object id!')
                            subdict[subkey] = ObjectId(subdict[subkey])
            elif "_id" == key:
                # print('this is an _id, wrap it in an object id!')
                query_to_run[key] = ObjectId(query_to_run[key])
                # print(f'query to run is now {query_to_run}'
                query_to_run = query_to_run
        # now run the query
        result = table.find_one(
            query_to_run
        )
        # self.close_conn()
        if result is not None:
            for key, value in result.items():
                if isinstance(value, ObjectId):
                    result[key] = str(result[key])
                if isinstance(value, datetime.datetime):
                    result[key] = str(datetime.datetime.now())
            return result
        else:
            return None

    def run_find_many_query(self, table, query_to_run):
        for key, value in query_to_run.items():
            if '$' in key:  # this means we are doing and and or or, which means a list of dictionaries
                for subdict in value:  # for each sub dictionary in the list
                    for subkey, subvalue in subdict.items():  # iterate through each dict and update
                        if "_id" == subkey or "user" in subkey or "ID" in subkey or "account" in subkey:
                            # print('this is an _id, wrap it in an object id!')
                            subdict[subkey] = ObjectId(subdict[subkey])
            elif "_id" == key or "user" in key or "ID" in key or "account" in key:
                # print('this is an _id, wrap it in an object id!')
                query_to_run[key] = ObjectId(query_to_run[key])
                # print(f'query to run is now {query_to_run}'
                query_to_run = query_to_run

        result_list = table.find(
            query_to_run
        )
        # self.close_conn()
        find_many_result = [result for result in result_list if result_list is not None]
        if len(find_many_result) > 0:
            for result in find_many_result:
                for key, value in result.items():
                    if isinstance(value, ObjectId):
                        result[key] = str(result[key])
            return find_many_result
        else:
            return None

    def update_all_records(self, table_name, set_fields_query):
        db = self.select_collection(table_name)
        db.update_many(
            {},
            {
                "$set": set_fields_query
            }
        )

    def set_field_for_object_in_table(self, table, record_id_to_update: str, query_to_run: dict):
        table.update_one(
            {
                '_id': ObjectId(record_id_to_update)
            },
            {
                "$set": query_to_run
            }
        )

    def delete_many_query(self, table_name, query_to_run):
        db = self.select_collection(table_name)
        for key, value in query_to_run.items():
            if '$' in key:  # this means we are doing and and or or, which means a list of dictionaries
                for subdict in value:  # for each sub dictionary in the list
                    for subkey, subvalue in subdict.items():  # iterate through each dict and update
                        if "_id" == subkey or "user" in subkey or "ID" in subkey or "account" in subkey:
                            # print('this is an _id, wrap it in an object id!')
                            subdict[subkey] = ObjectId(subdict[subkey])
            # user has to be an == not an 'in' since username is NOT an object ID
            elif "_id" == key or "user" == key or "ID" in key or "account" in key:
                # print('this is an _id, wrap it in an object id!')
                query_to_run[key] = ObjectId(query_to_run[key])
                # print(f'query to run is now {query_to_run}'
                query_to_run = query_to_run

        db.delete_many(
            query_to_run
        )

    def insert_contact(self, discord_id, name, phone, address, birthday, email, summoner_id=None, share_with=[]):
        db = self.select_collection('contacts')
        results = db.insert_one(
            {
                "disc_id": discord_id,
                "details": {
                    "name": name,
                    "phone": phone,
                    "address": address,
                    "dob": birthday,
                    "email": email
                },
                "summoner_id": summoner_id,
                "share_with": share_with
            }
        )
        return results
