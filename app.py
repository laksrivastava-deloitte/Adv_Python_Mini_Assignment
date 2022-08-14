from crypt import methods
from email import message
from genericpath import exists
from locale import currency
from sched import scheduler
from flask import Flask, request,jsonify, make_response, Response
from models.movie_item import MovieItem
from models.user import User

import time
from flask import g

import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler

from boto3.dynamodb.conditions import Key, Attr


app = Flask(__name__)

#Run on all request
@app.before_request
def before_request_time():
    g.start=time.time()

#Run on all request
@app.after_request
def after_request_time(response):
    time_diff=int((time.time()- g.start)*1000)
    response.headers["X-TIME-TO-EXECUTE"] = f"{time_diff} ms."
    return response

scheduler = BackgroundScheduler()
def csv_dynamodb_sync():
    try:
        MovieItem.sync_with_csv()
    except:
        # scheduler.shutdown()
        print("Invalid input in CSV")

scheduler.add_job(csv_dynamodb_sync, 'interval', seconds=5)
scheduler.start()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']

        if not token:
            return jsonify({'message' : 'Token is missing!'}), 401

        try: 
            SECRET_KEY = 'thisissecret'
            data = jwt.decode(token,SECRET_KEY)
            current_user = User.find_user_by_name(data['name'])
            # print(current_user)
        except:
            return jsonify({'message' : 'Token is invalid!'}), 401

        return f(current_user, *args, **kwargs)

    return decorated


#Create User Table
@app.route('/createUserTable')
def create_user_table():
    is_user_table_created = User.create_table_user()
    if is_user_table_created:
        return {'message': 'User table created successfully'}
    else:
        return {'message': 'User Table already exists'}, 400

#Create Movie Table
@app.route('/createTable')
@token_required
def create_table(current_user):
    if(not current_user['Item']['is_admin']):
        return {"message":"Only admin are allowed to use this functionality"},401
    is_movie_table_created = MovieItem.create_table_movie()
    if is_movie_table_created:
        return {'message': 'Movie table created successfully'}
    else:
        return {'message': 'Movie Table already exists'}, 400

#Load Movies from CSV FIle
@app.route('/loadMovie')
@token_required
def load_movie(current_user):
    if(not current_user['Item']['is_admin']):
        return {"message":"Only admin are allowed to use this functionality"},401
    MovieItem.upload_data_in_table()
    return {'message': 'Movie loaded from csv successfully'}

#Delete Movie Table
@app.route('/deleteTable', methods=['DELETE'])
@token_required
def delete_table(current_user):
    if(not current_user['Item']['is_admin']):
        return {"message":"Only admin are allowed to use this functionality"},401
    table_deleted = MovieItem.delete_table_movie()
    if table_deleted:
        return {'message': 'Movie table deleted successfully'}, 200
    else:
        return {'message': 'Movie Table not exists'}, 400

#Delete User Table
@app.route('/deleteUserTable', methods=['DELETE'])
@token_required
def delete_user_table(current_user):
    if(not current_user['Item']['is_admin']):
        return {"message":"Only admin are allowed to use this functionality"},401
    table_deleted = User.delete_table_user()
    if table_deleted:
        return {'message': 'User table deleted successfully'}, 200
    else:
        return {'message': 'User Table not exists'}, 400

# Question: 1
@app.route('/titles',methods=['POST'])
@token_required
def get_titles(current_user):
    data = request.get_json()
    print(data)
    response = MovieItem.movie_table.scan(
        FilterExpression=Attr('director').eq(data['director']) & Attr('year').between(int(data['start_year']),int(data['end_year'])),
        ProjectionExpression = 'id,title'
    )
    return {"Count":response['Count'],"Items":response['Items']}

# Question: 2
@app.route('/reviewFilter',methods=['POST'])
@token_required
def get_review_filtered_titles(current_user):
    data = request.get_json()
    response=MovieItem.movie_table.scan(
        FilterExpression=Attr('reviews_from_users').gt(data['review'])& Attr('language').eq(data['language']),
        ProjectionExpression = 'id,title,reviews_from_users'
    )
    return {'Count':response['Count'],"Data":sorted(response['Items'],key=lambda x:int(x['reviews_from_users']),reverse=True)}

def compare_amt(year,amt,dict_year,item,currency_conversion):
    year=int(year)
    if(amt.find('$')!=-1):
        amt=amt[2:-2]
        while(amt.find(',')!=-1):
            index=amt.find(',')
            amt=amt[:index]+amt[index+1:]
        amt=float(amt)
    else:
        currency_name=amt[:3]
        amt=amt[4:].strip()
        amt=float(amt)*currency_conversion[currency_name]

    if(dict_year.get(year)):
        if(dict_year[year]['budget']>amt):
            pass
        else:
            dict_year[year]={'budget':amt,'value':item}
    else:
        dict_year[year]={'budget':amt,'value':item}

# Question: 3
@app.route('/budgetTitle',methods=['POST'])
@token_required
def get_highest_budget_titles(current_user):
    data = request.get_json()
    response=MovieItem.movie_table.scan(
        FilterExpression=Attr('country').eq(data['country']),
        ExpressionAttributeNames = {'#c': 'year'},
        ProjectionExpression = 'id,title,#c,budget,country'
    )

    dict_year={}
    currency_conversion={'ITL':0.000530062,'ROL':0.21,'SEK':0.098,'FRF':1.03,'NOK':0.10,'GBP':1.21,'DEM':0.524262}
    for i in response['Items']:
        if(len(i['budget'])>1):
            compare_amt(i['year'],i['budget'],dict_year,i,currency_conversion)
    # print(dict_year)
    return dict_year

#Get Single Movie
@app.route('/getMovie/<string:id>')
@token_required
def find_movie(current_user,id):
    response = MovieItem.find_movie_by_id(id)
    if(response.get('Item')):
        return {'data': response.get('Item')}, 200
    else:
        return {'message': 'movie not found'}, 400

@app.route('/getUser/<string:id>')
def find_user(name):
    response = User.find_user_by_id(name)
    if(response.get('Item')):
        return {'data': response.get('Item')}, 200
    else:
        return {'message': 'movie not found'}, 400

#Get All Movie
@app.route('/getAllMovie')
@token_required
def find_all_movie(current_user):
    return {"movieList": MovieItem.get_all_movie()}

#Get All Users
@app.route('/getAllUser')
@token_required
def find_all_user(current_user):
    if(not current_user['Item']['is_admin']):
        return {"message":"Only admin are allowed to use this functionality"},401
    return {"userList": User.get_all_users()}

#Update Movie
@app.route('/updateMovie/<string:id>', methods=['PUT'])
@token_required
def update_movie(current_user,id):
    if(not current_user['Item']['is_admin']):
        return {"message":"Only admin are allowed to use this functionality"},401
    data = request.get_json()
    movie_obj = MovieItem(data)
    response = movie_obj.update_movie(id)
    return {'message': 'Movie updated Successfully', 'updated field': response['Attributes']}

#Create single movie
@app.route('/createMovie', methods=['POST'])
@token_required
def create_movie(current_user):
    if(not current_user['Item']['is_admin']):
        return {"message":"Only admin are allowed to use this functionality"},401
    data = request.get_json()
    movie_obj = MovieItem(data)
    response = movie_obj.insert_movie()
    if response:
        new_movie_obj = MovieItem.find_movie_by_id(data['id'])
        return {'message': 'movie created successfully', 'data': new_movie_obj['Item']}
    else:
        return {'result': 'Failed', "message": 'movie with same id already exists'}, 400

#User/Admin Registration
@app.route('/registration', methods=['POST'])
def create_user():
    data = request.get_json()
    data['password']=generate_password_hash(data['password'], method='sha256')
    user_obj = User(**data)
    response = user_obj.insert_user()
    if response:
        new_user_obj = User.find_user_by_name(data['name'])
        return {'message': 'User created successfully', 'data': new_user_obj['Item']}
    else:
        return {'result': 'Failed', "message": 'user with same name already exists'}, 400


@app.route('/deleteMovie/<string:id>', methods=['DELETE'])
@token_required
def delete_movie(current_user,id):
    if(not current_user['Item']['is_admin']):
        return {"message":"Only admin are allowed to use this functionality"},401
    response = MovieItem.delete_from_movie(id)
    if 'ConsumedCapacity' in response.keys():
        return {'message': 'Movie not found'}, 400
    else:
        return {'message': f'Movie with id {id} deleted successfully'}, 200

@app.route('/deleteUser/<string:name>', methods=['DELETE'])
def delete_user(name):
    response = User.delete_user(name)
    if 'ConsumedCapacity' in response.keys():
        return {'message': 'User not found'}, 400
    else:
        return {'message': f'User with name {name} deleted successfully'}, 200



@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    name = data['name']
    password = data['password']
    response = None
    if not name or not password:
        return {'message':"name and password field not present"},400

    user = User.find_user_by_name(name=name)
    
    if 'Item' not in user.keys():
        return {"message":"Invalid Credentials"},400

    user=user['Item']

    SECRET_KEY = 'thisissecret'
    if check_password_hash(user['password'], password):
        token = jwt.encode({'name' : user['name'], 'exp' : datetime.datetime.utcnow() + datetime.timedelta(minutes=120)}, SECRET_KEY)

        response = jsonify({'token' : token.decode('UTF-8')})
        return response

    return {"message":"Invalid Credentials"},400


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
    # app.run(port=5000, debug=True)
