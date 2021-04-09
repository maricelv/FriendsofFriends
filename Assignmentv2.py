import twitter
from functools import partial
from sys import maxsize as maxint
import sys
import time
from urllib.error import URLError
from http.client import BadStatusLine
import json
import networkx as nx
import matplotlib.pyplot as plt




auth = twitter.oauth.OAuth(OAUTH_TOKEN, OAUTH_TOKEN_SECRET,
                                       CONSUMER_KEY, CONSUMER_SECRET)

api = twitter.Twitter(auth=auth)
# From Cookbook
def make_twitter_request(twitter_api_func, max_errors=10, *args, **kw): 
    
    # A nested helper function that handles common HTTPErrors. Return an updated
    # value for wait_period if the problem is a 500 level error. Block until the
    # rate limit is reset if it's a rate limiting issue (429 error). Returns None
    # for 401 and 404 errors, which requires special handling by the caller.
    def handle_twitter_http_error(e, wait_period=2, sleep_when_rate_limited=True):
    
        if wait_period > 3600: # Seconds
            print('Too many retries. Quitting.', file=sys.stderr)
            raise e
    
        # See https://developer.twitter.com/en/docs/basics/response-codes
        # for common codes
    
        if e.e.code == 401:
            print('Encountered 401 Error (Not Authorized)', file=sys.stderr)
            return None
        elif e.e.code == 404:
            print('Encountered 404 Error (Not Found)', file=sys.stderr)
            return None
        elif e.e.code == 429: 
            print('Encountered 429 Error (Rate Limit Exceeded)', file=sys.stderr)
            if sleep_when_rate_limited:
                print("Retrying in 15 minutes...ZzZ...", file=sys.stderr)
                sys.stderr.flush()
                time.sleep(60*15 + 5)
                print('...ZzZ...Awake now and trying again.', file=sys.stderr)
                return 2
            else:
                raise e # Caller must handle the rate limiting issue
        elif e.e.code in (500, 502, 503, 504):
            print('Encountered {0} Error. Retrying in {1} seconds'                  .format(e.e.code, wait_period), file=sys.stderr)
            time.sleep(wait_period)
            wait_period *= 1.5
            return wait_period
        else:
            raise e

    # End of nested helper function
    
    wait_period = 2 
    error_count = 0 

    while True:
        try:
            return twitter_api_func(*args, **kw)
        except twitter.api.TwitterHTTPError as e:
            error_count = 0 
            wait_period = handle_twitter_http_error(e, wait_period)
            if wait_period is None:
                return
        except URLError as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print("URLError encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                print("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise
        except BadStatusLine as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print("BadStatusLine encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                print("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise

# Sample usage

twitter_api = api

# See http://bit.ly/2Gcjfzr for twitter_api.users.lookup

#response = make_twitter_request(twitter_api.users.lookup, 
                                #screen_name="marceyreads")

#print(json.dumps(response, indent=1))
# From Cookbook
def get_friends_followers_ids(twitter_api, screen_name=None, user_id=None,
                              friends_limit=maxint, followers_limit=maxint):
    
    # Must have either screen_name or user_id (logical xor)
    assert (screen_name != None) != (user_id != None),     "Must have screen_name or user_id, but not both"
    
    # See http://bit.ly/2GcjKJP and http://bit.ly/2rFz90N for details
    # on API parameters
    
    get_friends_ids = partial(make_twitter_request, twitter_api.friends.ids, 
                              count=5000)
    get_followers_ids = partial(make_twitter_request, twitter_api.followers.ids, 
                                count=5000)

    friends_ids, followers_ids = [], []
    
    for twitter_api_func, limit, ids, label in [
                    [get_friends_ids, friends_limit, friends_ids, "friends"], 
                    [get_followers_ids, followers_limit, followers_ids, "followers"]
                ]:
        
        if limit == 0: continue
        
        cursor = -1
        while cursor != 0:
        
            # Use make_twitter_request via the partially bound callable...
            if screen_name: 
                response = twitter_api_func(screen_name=screen_name, cursor=cursor)
            else: # user_id
                response = twitter_api_func(user_id=user_id, cursor=cursor)

            if response is not None:
                ids += response['ids']
                cursor = response['next_cursor']
        
            print('Fetched {0} total {1} ids for {2}'.format(len(ids),                  label, (user_id or screen_name)),file=sys.stderr)
        
            # XXX: You may want to store data during each iteration to provide an 
            # an additional layer of protection from exceptional circumstances
        
            if len(ids) >= limit or response is None:
                break

    # Do something useful with the IDs, like store them to disk...
    return friends_ids[:friends_limit], followers_ids[:followers_limit]


# Sample usage

#twitter_api = api

# friends_ids, followers_ids = get_friends_followers_ids(twitter_api, 
#                                                        screen_name="marceyreads", 
#                                                        friends_limit=5000, 
#                                                        followers_limit=5000)

#print(friends_ids)
#print(followers_ids)

# print(json.dumps(reciprocal_friends, indent=1,sort_keys=True))

# Reciprocal Friends
def reciprocal_friends(friends_ids, followers_ids):
    set3 = set(friends_ids) 
    set2= set(followers_ids) #find the intersection of the two
    set1 = set3 & set2 #reciprocal_friends
    reciprocal = list(set1)  #turns the set to a list
    return reciprocal #returns the list of mutual friends


# From Cookbook
def get_user_profile(twitter_api, screen_names=None, user_ids=None):
   
    # Must have either screen_name or user_id (logical xor)
    assert (screen_names != None) != (user_ids != None),     "Must have screen_names or user_ids, but not both"
    
    items_to_info = {}

    items = screen_names or user_ids
    
    while len(items) > 0:

        # Process 100 items at a time per the API specifications for /users/lookup.
        # See http://bit.ly/2Gcjfzr for details.
        
        items_str = ','.join([str(item) for item in items[:100]])
        items = items[100:]

        if screen_names:
            response = make_twitter_request(twitter_api.users.lookup, 
                                            screen_name=items_str)
        else: # user_ids
            response = make_twitter_request(twitter_api.users.lookup, 
                                            user_id=items_str)
    
        for user_info in response:
            if screen_names:
                items_to_info[user_info['screen_name']] = user_info
            else: # user_ids
                items_to_info[user_info['id']] = user_info

    return items_to_info

def popular(reciprocal): #Get the 5 most popular reciprocal friends
# Get Reciprocal Friends
# Find most popular Reciprocal Friend with Most Followers
    reciprocal_followers = get_user_profile(twitter_api, user_ids=reciprocal)
    if len(reciprocal_followers)<=5:
        return reciprocal_followers
# Sort list of reciprocal friends
    dit = {id:reciprocal_followers[id]['followers_count'] for id in reciprocal_followers.keys()}

    sort = sorted(dit, key = dit.get, reverse = True)
        
    return sort[:5] #if len(dit) > 5 else sort[:]




# Use a crawler to get distance-2,d3,d4 friends and follow
def crawl_followers(twitter_api, screen_name, user_id=None): #from cookbook but modified

    G = nx.Graph() #graph name
    friends_ids, followers_ids = get_friends_followers_ids(twitter_api, screen_name=screen_name, friends_limit=5000, followers_limit=5000)
    # Find the reciprocal friends for first user
    response = popular(reciprocal_friends(friends_ids, followers_ids))
    print("Top 5 Reciprocal Friends is ", response)
    #Need the first id, then the next ids runs through the loop
    user_id = 165035772
    for i in response:
        G.add_edge(user_id, i)

    next_queue = response
    
    depth = 1 #root node
    collectedHundred = False
    max_depth = 1000
    # Find the reciprocal friends for the friends list
    while depth < max_depth and not collectedHundred:
        depth += 1
        (queue, next_queue) = (next_queue, []) #sets the queue as the top 5 friends and next_ queue as a empty list for the next group of top 5 friends for each user/node
        for id in queue: #repeats getting the top 5 for each user
            friends_ids, followers_ids = get_friends_followers_ids(twitter_api, user_id=id, friends_limit=5000, followers_limit=5000)
            response = popular(reciprocal_friends(friends_ids, followers_ids))
            print("Top 5 Reciprocal Friends for id:",id,"is ", response)
            for i in response:
                if (i not in next_queue and i not in G.nodes()): next_queue.append(i)
            for i in response:
                G.add_edge(id, i)
            # If the number of nodes exceeds 100, then break
            if (G.number_of_nodes() >= 100):
                collectedHundred = True
                break

    print("Number of Nodes = {0}".format(nx.number_of_nodes(G)))
    #Collect the nodes and draw the graph using subgraphs
    connected_component_subgraphs = (G.subgraph(c) for c in nx.connected_components(G))
    sg = max(connected_component_subgraphs, key=len)
    print("The diameter is {0}".format(nx.diameter(sg)))
    print("The average distance is {0}".format(nx.average_shortest_path_length(sg)))
    # Draw the graph using matplot
    nx.draw(G, node_color='cyan', with_labels=True)
    plt.savefig("graph.png")
    plt.show()


# Sample usage
name = "lady□bird"

name[5] = 'X'

print(name)


#print(get_user_profile(twitter_api, screen_names=["SocialWebMining", "ptwobrussell"]))
#popular(twitter_api, user_ids= reciprocal_friends([1,2,3,4,5], [6,7,8,9]))
#crawl_followers(twitter_api, screen_name='edmundyu1001')
#reciprocal_friends([1,2,3,4], [1,2,3,4])
#print(json.dumps(r, indent=1,sort_keys=True))
#print(get_friends_followers_ids(twitter_api, screen_name='marceyreads'))

