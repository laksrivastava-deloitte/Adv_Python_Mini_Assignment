from unicodedata import decimal
from urllib import response
from boto3 import resource
import csv
import config
import re

class MovieItem:

    regex = re.compile(r"\\.|[\",]", re.DOTALL)

    ALL_ATTRIBUTES = ['id', 'title', 'original_title', 'year', 'date_published', 'genre', 'duration', 'country', 'language', 'director', 'writer', 'production_company',
                      'actors', 'description', 'avg_vote', 'votes', 'budget', 'usa_gross_income', 'worlwide_gross_income', 'metascore', 'reviews_from_users', 'reviews_from_critics']

    resource = resource(
        'dynamodb',
        endpoint_url=config.ENDPOINT_URL,
        aws_access_key_id=config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
        region_name=config.REGION_NAME
    )

    #Table Movie is linked by variable
    movie_table = resource.Table('Movie')

    #Helper function for csv_to_list     :convert , seperated line to list
    @staticmethod
    def parts(data):
        delimiter = ''
        compos = [-1]
        for match in MovieItem.regex.finditer(data):
            g = match.group(0)
            if delimiter == '':
                if g == ',':
                    compos.append(match.start())
                elif g in "\"":
                    delimiter = g
            elif g == delimiter:
                delimiter = ''
        # you may uncomment the next line to catch errors
        #if delimiter: raise ValueError("Unterminated string in data")
        compos.append(len(data))
        return [ data[compos[i]+1:compos[i+1]] for i in range(len(compos)-1)]

    #Helper function for upload_data_in_table    :return all movies in list
    @staticmethod
    def csv_to_list():
        with open('movies.csv', 'r') as f:
            results = []
            first = True
            for line in f:
                words = MovieItem.parts(line)
                if first:
                    first = False
                    continue
                for i in [3,6,15,20]:
                    if(len(words[i])>0):
                        words[i]=int(words[i])
                if(len(words[21])>1):
                    words[i]=int(words[21][:-1])
                results.append(words)
            return results

    @staticmethod
    def upload_data_in_table():
    # create_table_movie()
        data=MovieItem.csv_to_list()
        for i in range(len(data)):
            dict_data={}
            j=0
            for key in MovieItem.ALL_ATTRIBUTES:
                dict_data[key]=data[i][j]
                j=j+1
            movie_obj=MovieItem(dict_data)
            movie_obj.insert_movie()

    def __init__(self, movie_dict):
        self.movie_dict = movie_dict

    def insert_movie(self):
        movie_obj= self.find_movie_by_id(self.movie_dict['id'])
        if(movie_obj.get('Item')):
            return None
        else:
            for key in MovieItem.ALL_ATTRIBUTES:
                if key not in self.movie_dict:
                    self.movie_dict[key]=""
            response = MovieItem.movie_table.put_item(
                Item={
                    **self.movie_dict
                }
            )
        return response

    @staticmethod
    def find_movie_by_id(id):
        response = MovieItem.movie_table.get_item(
            Key = {
                'id'     : id
            },
            AttributesToGet = MovieItem.ALL_ATTRIBUTES
        )
        return response

    @staticmethod
    def get_all_movie():
        return MovieItem.movie_table.scan().get('Items')

    def update_movie(self,id):
        temp_dict={}
        for key in self.movie_dict.keys():
            if(self.movie_dict[key]):
                temp_dict[key]={'Value':self.movie_dict[key],'Action':'PUT'}
        print("temp_dict: ",temp_dict)
        response= MovieItem.movie_table.update_item(Key={'id':id},AttributeUpdates={**temp_dict},ReturnValues = "UPDATED_NEW")
        return response

    @staticmethod
    def delete_from_movie(id):
        response = MovieItem.movie_table.delete_item(
            Key = {
                'id': id
            }
        )
        return response

    @staticmethod
    def create_table_movie():
        table_name = 'Movie'
        table_names = [table.name for table in MovieItem.resource.tables.all()]
        if table_name not in table_names:    
            MovieItem.resource.create_table(
                TableName = table_name, # Name of the table 
                KeySchema = [
                    {
                        'AttributeName': 'id',
                        'KeyType'      : 'HASH' # HASH = partition key, RANGE = sort key
                    }
                ],
                AttributeDefinitions = [
                    {
                        'AttributeName': 'id', # Name of the attribute
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
    def delete_table_movie():
        table_name = 'Movie'
        table_names = [table.name for table in MovieItem.resource.tables.all()]
        if table_name in table_names:
            MovieItem.movie_table.delete()
            return True
        else:
            return False
    
    #Run Ater every fixed interval of time
    @staticmethod
    def sync_with_csv():
        #Will check file from last
        with open('movies.csv','r') as file:
            for row in reversed(list(csv.reader(file))):
                movie_item=MovieItem.find_movie_by_id(row[0])
                if 'Item' in movie_item.keys():
                    print("Everything is synced")
                    break
                else:
                    index,data=0,{}
                    for i in MovieItem.ALL_ATTRIBUTES:
                        data[i]=row[index]
                        index=index+1
                    response = MovieItem.movie_table.put_item(
                        Item=data
                    )
                    movie_item=MovieItem.find_movie_by_id(data['id'])
                    print("New Data Added: ",movie_item['Item'])

        

    
