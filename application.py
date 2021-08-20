import os
import requests
import json

from flask import Flask, session, render_template, request, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/", methods=["POST", "GET"])
def index():
    #el error puede estar aquí
    if not session.get("logged_in"):
        return render_template("login.html")
    else:
        username=session.get("username")
        session_on = 1
        return render_template("index.html", session_on=session_on, username=username)


@app.route("/register", methods=["POST", "GET"])
def register():
    if request.method == "POST":
        if not request.form.get("username"):
            return render_template("error.html", message="Must provide username")

        username=request.form.get("username")
        password=request.form.get("password")
        confirmation=request.form.get("confirmation")
        userCheck = db.execute("SELECT * FROM users WHERE username = :username", {"username":username}).fetchone()
        if userCheck:
            return render_template("error.html", message="Username already exist")

        elif not password:
            return render_template("error.html", message="Must provide password")

        elif not password:
            return render_template("error.html", message="Must confirm password")

        elif not password == confirmation:
            return render_template("error.html", message="Passwords didn't match")

        hashedPassword=generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)

        db.execute("INSERT INTO users (username, password) VALUES (:username, :password)",{"username":username, "password":hashedPassword})

        db.commit()

        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/login", methods=["POST", "GET"])
def login():

    if request.method == "GET":
        if session.get("logged_in"):
            return render_template("index.html")
        else:
            render_template("login.html")

    if request.method == "POST":
        username=request.form.get("username")
        password=request.form.get("password")
        if not request.form.get("username"):
            return render_template("error.html", message="Must provide username")

        elif not request.form.get("password"):
            return render_template("error.html", message="Must provide password")

        res = db.execute("SELECT * FROM users WHERE username = :username", {"username": username})

        result = res.fetchone()

        if result == None or not check_password_hash(result[2], password):
            return render_template("error.html", message="Invalid username or password")

        # session["user_id"]=result[0]
        # session["user_name"]=result[1]

        session["logged_in"]=True
        session["username"]=username

        return redirect("/")
        # return render_template("book.html", username=username)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    session["logged_in"]=False
    return redirect(url_for("login"))


@app.route("/search", methods=["POST"])
def search():
    if session.get("logged_in"):
        username=session.get("username")
        session_on = 1
        session["books"]=[] 
        if request.method=="POST":
            if not request.form.get("text"):
                return render_template("error.html", session_on=session_on,username=username, message="Enter some data of a book")
            text=request.form.get("text")
            data=db.execute("SELECT * FROM books WHERE author iLIKE '%"+text+"%' OR title iLIKE '%"+text+"%' OR isbn iLIKE '%"+text+"%'").fetchall()
            for x in data:
                session["books"].append(x)
            if len(session["books"])==0:
                return render_template("error.html", session_on=session_on,username=username, message="Book not found. Try again.")
                            
        return render_template("book.html", data=session["books"], session_on=session_on, username=username)

    else:
        render_template("login.html")


@app.route("/isbn/<string:isbn>",methods=["GET","POST"])
def bookpage(isbn):
    warning=""
    username=session.get("username")
    session_on = 1
    session["reviews"]=[]
    secondreview=db.execute("SELECT * FROM reviews WHERE isbn = :isbn AND username= :username",{"username":username,"isbn":isbn}).fetchone()
    if request.method=="POST" and secondreview==None:
        review=request.form.get('textarea') 
        rating=request.form.get('stars')
        db.execute("INSERT INTO reviews (isbn, review_text, rating, username) VALUES (:isbn,:review_text,:rating,:username)",{"isbn":isbn,"review_text":review,"rating":rating,"username":username})
        db.commit()
    if request.method=="POST" and secondreview!=None:
        warning="Sorry. You cannot add second review."
    
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "olpNbYYc48bX0vRhxTbFnA", "isbns": isbn})
    average_rating=res.json()['books'][0]['average_rating']
    work_ratings_count=res.json()['books'][0]['work_ratings_count']
    reviews=db.execute("SELECT * FROM reviews WHERE isbn = :isbn",{"isbn":isbn}).fetchall() 
    for y in reviews:
        session['reviews'].append(y)  
    data=db.execute("SELECT * FROM books WHERE isbn = :isbn",{"isbn":isbn}).fetchone()
    return render_template("reviews.html",data=data,reviews=session['reviews'],average_rating=average_rating,work_ratings_count=work_ratings_count,username=username,warning=warning, session_on=session_on)


@app.route("/api/<string:isbn>")
def api(isbn):
    data=db.execute("SELECT * FROM books WHERE isbn = :isbn",{"isbn":isbn}).fetchone()
    if data==None:
        return jsonify({"error": "Invalid book isbn"})
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "olpNbYYc48bX0vRhxTbFnA", "isbns": isbn})
    average_rating=res.json()['books'][0]['average_rating']
    work_ratings_count=res.json()['books'][0]['work_ratings_count']

    return jsonify({
        "title": data.title,
        "author": data.author,
        "year": data.year,
        "isbn": isbn,
        "review_count": work_ratings_count,
        "average_score": average_rating
    })
