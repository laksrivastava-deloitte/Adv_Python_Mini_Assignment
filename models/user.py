from boto3 import resource
import config
class User:

    resource = resource(
        'dynamodb',
        endpoint_url=config.ENDPOINT_URL,
        aws_access_key_id=config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
        region_name=config.REGION_NAME
    )

    ALL_ATTRIBUTES = ['name','password','is_admin']

    user_table = resource.Table('User')

    def __init__(self,name,password,is_admin=False):
        self.name=name
        self.password=password
        self.is_admin=is_admin

    @staticmethod
    def create_table_user():
        table_name = 'User'
        table_names = [table.name for table in User.resource.tables.all()]
        if table_name not in table_names:    
            User.resource.create_table(
                TableName = table_name, # Name of the table 
                KeySchema = [
                    {
                        'AttributeName': 'name',
                        'KeyType'      : 'HASH' # HASH = partition key, RANGE = sort key
                    }
                ],
                AttributeDefinitions = [
                    {
                        'AttributeName': 'name', # Name of the attribute
                        'AttributeType': 'S'   
                    }
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits'  : 10,
                    'WriteCapacityUnits': 10
                }
            )
            return True
        else:
            return False
    
    @staticmethod
    def delete_table_user():
        table_name = 'User'
        table_names = [table.name for table in User.resource.tables.all()]
        if table_name in table_names:
            User.user_table.delete()
            return True
        else:
            return False

    @staticmethod
    def get_all_users():
        return User.user_table.scan().get('Items')

    @staticmethod
    def find_user_by_name(name):
        response = User.user_table.get_item(
            Key = {
                'name'     : name
            },
            AttributesToGet = User.ALL_ATTRIBUTES
        )
        return response

    def insert_user(self):
        user_obj= self.find_user_by_name(self.name)
        if(user_obj.get('Item')):
            return None
        else:
            response = User.user_table.put_item(
                Item={
                    'name':self.name,
                    'password':self.password,
                    'is_admin':self.is_admin
                }
            )
        return response

    @staticmethod
    def delete_user(name):
        response = User.user_table.delete_item(
            Key = {
                'name': name
            }
        )
        return response