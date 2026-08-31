from config import settings
import httpx
from models import User, Post
import asyncio
from storage import create_db, insert_users, insert_posts, insert_failed_records
from pydantic import ValidationError

#extract

async def fetch(client,url):
    for attempt in range(3):
        try:
            response = await client.get(url,timeout=5)
            response.raise_for_status()

            return response.json()

        except httpx.TimeoutException:
            print(f"Attempt {attempt+1} failed")
            if attempt<2:
                wait_time = 2**attempt
                print(f"Retrying in {wait_time} seconds")
                await asyncio.sleep(wait_time)
            else:
                print("All attempts failed")
                return None

        except httpx.HTTPError as e:
            print(f"HTTP error: {e}")
            return None

#main pipeline
async def main():

    create_db()

    #extract
    async with httpx.AsyncClient() as client:
        users_task = fetch(client,settings.users_url)
        posts_task = fetch(client,settings.posts_url)
      
        
        users_data,posts_data = await asyncio.gather(users_task,posts_task)

        if users_data is None:
            users_data=[]
        if posts_data is None:
             posts_data=[]

        #users_data[0]["id"] = "INVALID" 
        # used for testing purpose

        #validate
        users = []
        failed_users = []

        for user in users_data:
            try:
                validated_user = User(**user)
                users.append(validated_user)
            except ValidationError as e:
                failed_users.append({
                    "source":"users",
                    "record":user,
                    "error":str(e)
                })

        posts = []
        failed_posts = []

        for post in posts_data:
            try:
                validated_post = Post(**post)
                posts.append(validated_post)
            except ValidationError as e:
                failed_posts.append({
                    "source": "posts",
                    "record": post,
                    "error": str(e)
                })

        print(f"Valid users: {len(users)}")
        print(f"Failed users: {len(failed_users)}")

        print(f"Valid posts: {len(posts)}")
        print(f"Failed posts: {len(failed_posts)}") 

        #transform
        users_transf = [
            {
                "id": user.id,
                "name": user.name,
                "email": user.email
            }
            for user in users
        ]
        posts_transf = [
            {
                "id": post.id,
                "user_id": post.userId,
                "title": post.title
            }
            for post in posts
        ]

        #data ingestion
        insert_users(users_transf)
        insert_posts(posts_transf)

        failed_rec = failed_users+failed_posts
        if failed_rec:
            insert_failed_records(failed_rec)

        print("Data loaded")

   
if __name__ == "__main__":
    asyncio.run(main())




