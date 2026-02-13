import base64
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from fastapi import FastAPI, HTTPException, Query, Request, Depends
from typing import Any,Annotated, Generic, Optional, TypeVar
from random import randint
from sqlmodel import create_engine, SQLModel, Session, func, select, Field
from pydantic import BaseModel


#data types creation------------------------------- basically the model we'll be using

class Campaign(SQLModel, table=True): # this one is connected to the base table that is why true
    campaign_id: int = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    due_date: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory= lambda:datetime.now(timezone.utc), nullable=True, index=True) 
    #here we don't want to invoke the function in default btttt we do wanna give arguuments which is difficult to do without the brackets thus we make use of the lambda function

class CampaignCreate(SQLModel):
    name: str
    due_date: datetime |None = None
#---------------db creation
sqlite_file_name= "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}" #connection string
connect_args={"check_same_thread":False}
engine = create_engine(sqlite_url, connect_args=connect_args)
# app = FastAPI(root_path="/api/v1")

#func to create tables
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

SessionDependency = Annotated[Session,Depends(get_session)]

#lifespan - startup and shutdown logic is defined using this parameter of fastapi and a contxt manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    with Session(engine) as session: #this stpe is optional, this is for storing some data(tables) inside the db file
        if not session.exec(select(Campaign)).first():
            session.add_all([ # pyright: ignore[reportCallIssue]
                Campaign(name="Summer Launch", due_date=datetime.now()),
                Campaign(name="Black Friday", due_date=datetime.now())
            ])
            session.commit()

    yield


app = FastAPI(root_path="/api/v1", lifespan=lifespan)
#if u ever get some roadblock just delete the db file and reload this code it'll come back again, though here we r actually initializing it with some data so that we do have something to work with
#------------------------------

@app.get("/")
async def root():
    return {"message": "Hello world!"}

data:Any  = [
    {
        "campaign_id": 1,
        "name": "Summer Launch",
        "due_date": datetime.now(),
        "created_at": datetime.now()
    },
    {
        "campaign_id": 2,
        "name": "Black Friday",
        "due_date": datetime.now(),
        "created_at": datetime.now()
    }
]

"""
Campaigns
- campaign_id
- name
- due_date
- created_at
"""
# class CampaignsResponse(BaseModel): # this helps define what is the structure that is to be expected of our data
#     campaigns:list[Campaign]
#new idea hehe let's work with more generic view
T = TypeVar("T")

class Response(BaseModel, Generic[T]):
    data: T


class PaginatedResponse(BaseModel,Generic[T]):
     #custome response
     data:T
     next:Optional[str]
    #  prev:Optional[str]
    #  count:int
def encode_cursor(value):
    raw = json.dumps({"id":value})
    return base64.urlsafe_b64encode(raw.encode()).decode() #the func was econding raw, but string doesn't get encoded thus raw is passed in binary format, and again decoded in string

def decode_cursor(cursor):
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    payload = json.loads(raw)
    return payload.get("id")

# square brackets show type all in here, before we were using ist of type campaign

@app.get("/campaigns", response_model=PaginatedResponse[list[Campaign]])
async def read_campaigns(request: Request, session: SessionDependency, cursor:Optional[str] = Query(None), limit: int =Query(20, ge=1)):#session dependency has to be passed to enable the access of db
    cursor_id = 0

    if cursor:
        cursor_id=decode_cursor(cursor)

    data = session.exec(select(Campaign).order_by(Campaign.campaign_id).where(Campaign.campaign_id>cursor_id).limit(limit+1)).all()

    base_url = str(request.url).split('?')[0]

    next_url = None

    if len(data)>limit:
        next_cursor = encode_cursor(data[:limit][-1].campaign_id)
        next_url = f"{base_url}?cursor={next_cursor}&limit={limit}"
   
    
    return {
        # "count":total,
        "next":next_url,
        # "prev":prev_url,
        "data": data[:limit]
    }

@app.get("/campaigns/{id}", response_model=Response[Campaign])
async def read_campaign(id: int, session: SessionDependency):
    data = session.get(Campaign, id)
    if not data: 
        raise HTTPException(status_code=404)
    return {"data": data}

@app.post("/campaigns", status_code=201, response_model=Response[Campaign])
async def create_campaign(campaign: CampaignCreate, session: SessionDependency):
    db_campaign = Campaign.model_validate(campaign)
    session.add(db_campaign)
    session.commit()
    session.refresh(db_campaign)
    return {"data": db_campaign}

@app.put("/campaigns/{id}", response_model=Response[Campaign])
async def update_campaign(id: int, campaign: CampaignCreate, session: SessionDependency):
    data = session.get(Campaign, id)
    if not data: 
        raise HTTPException(status_code=404)
    data.name = campaign.name
    data.due_date = campaign.due_date
    session.add(data)
    session.commit()
    session.refresh(data)
    return {"data": data}

@app.delete("/campaigns/{id}", status_code=204)
async def delete_campaign(id: int, session: SessionDependency):
    data = session.get(Campaign, id)
    if not data: 
        raise HTTPException(status_code=404)
    session.delete(data)
    session.commit()

"""""
@app.get("/campaigns") # this is called a decorator
async def read_campaigns():
    return {"campaigns": data}

@app.get("/campaigns/{id}")
async def read_campaign(id:int):
    for campaign in data:
        if campaign.get("campaign_id")==id:
            return{"campaign":campaign}
    raise HTTPException(status_code=404)

@app.post("/campaigns", status_code=201) # adding status code here to return data with a status code
# async def create_campaign(request: Request):
#     body = await request.json() here instead of writing these two distinctively we can just write the below statement that'll let the fastapi know that it has to provide a body for input
async def create_campaign(body: dict[str, Any]):
    new: Any = {
        "campaign_id": randint(100,1000),
        "name": body.get("name"),
        "due_date": body.get("due_date"),
        "created_at": datetime.now()
    }
    data.append(new)
    return {"campaign": new}

@app.put("/campaigns/{id}")
async def update_campaign(id: int, body:dict[str,Any]):
    for index, campaign in enumerate(data):
        if campaign.get("campaign_id")== id:
             updated: Any = {
                 "campaign_id": id,
                 "name": body.get("name"),
                 "due_date": body.get("due_date"),
                 "created_at": campaign.get("created_at")
            }
             data[index] = updated
             return{"campaign":updated}
    raise HTTPException(status_code=404)

@app.delete("/campaigns/{id}")
async def delete_campaign(id: int):
    for index, campaign in enumerate(data):
        if campaign.get("campaign_id")==id:
            data.pop(index)
            return Response(status_code=204)
    raise HTTPException(status_code=404) 

#now we make use of an orm that is object relational mapper to connect with a db
#this takes db records and converts them to objects in our code - also allows to skip over sql
#generally the big ones here are sql alchemy and sqlmodel
#sql model is often recommended for fast api as they have the same creators
#combination of sql alchemy and pydantic
"""
# this part was doing the working when we were giving the data manually and then asking it to work and so on
#the approach on top is the one whic actuually takes the data from the db and performs these operations on that data