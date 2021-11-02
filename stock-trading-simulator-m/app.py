from flask import Flask, render_template, make_response
import os
import time
import sqlite3
import os
import sqlite3
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, success

# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# connect to sqlite3 database
#connection = sqlite3.connect(r'C:\Users\milkt\Github-workspace\personal-projects\\financeTest\server\src\\finance.db', check_same_thread=False)
connection = sqlite3.connect(r"/app/finance.db", check_same_thread=False)
db = connection.cursor()

def format_server_time():
  server_time = time.localtime()
  return time.strftime("%I:%M:%S %p", server_time)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    # Forget any user_id
    session.clear()
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)
        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        # Query database for username
        db.execute("SELECT * FROM users WHERE username = :username", {"username": request.form.get("username")})
        # Save into a dictionary
        user_key = ["id", "username", "hash", "cash"]
        user_value = list(db.fetchone())
        if not user_value:
            return apology("account doesn't exist")
        user = {}
        for i in range(len(user_key)):
            user[user_key[i]] = user_value[i]
        # Ensure username exists and password is correct
        if not check_password_hash(user["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)
        # Remember which user has logged in
        session["user_id"] = user_value[0]
        session["username"] = user_value[1]
        # Redirect user to home page
        return redirect("/")
    else:
        return render_template("login.html")
      
@app.route('/')
def index():
    """Show portfolio of stocks"""
    # username, except when not logged in
    try:
        username = session["username"]
    except:
        KeyError
        return redirect("/login")
    #get the user cash amount
    db.execute("SELECT * FROM users WHERE id = :id", {"id": session["user_id"]})
    user_value = list(db.fetchone())
    user_key = ["id", "username", "hash", "cash"]
    user = {}
    for i in range(len(user_key)):
        user[user_key[i]] = user_value[i]

    # get the stock information in a dictionary
    db.execute("SELECT * FROM owned WHERE id = :id", {"id": session["user_id"]})
    stock_key = ["id", "symbol", "shares"] #PROBLEM 
    stock_value = list(db.fetchall())
    stocks = []
    # make a list of dictionaries for the stocks
    for stock in range(len(stock_value)):
        current_stock = {}
        for key in range(len(stock_value[stock])):
            current_stock[stock_key[key]] = stock_value[stock][key]
        stocks.append(current_stock)

    #make dicts that can pair values with the symbols in the array, and their usd format for display
    quotes = {}
    quotes_usd = {}
    values = {}
    values_usd = {}
    #total value of the porfolio
    porfolio_value = user["cash"]
    #interate through the stocks and save their quotes into two dicts for reference in index
    for stock in stocks:
        symbol = stock["symbol"]
        shares = int(stock["shares"])
        #search for stock price using lookup, then turn into usd format for display (this implementation takes more space tho...)
        quotes[stock["symbol"]] = lookup(stock["symbol"])
        quotes_usd[stock["symbol"]] = usd(quotes[stock["symbol"]]["price"])
        #calculate the total price for the stocks, then turn into usd format for display
        values[stock["symbol"]] = quotes[stock["symbol"]]["price"] * shares
        values_usd[stock["symbol"]] = usd(values[stock["symbol"]])
        #total value of the porfolio
        porfolio_value += (float(lookup(symbol)["price"]) * shares)
    #gotta remember to add your dicts to render_template!
    return render_template("index.html",
        username=username,
        user_cash=usd(user["cash"]),
        porfolio_value = usd(porfolio_value),
        stocks = stocks,
        quotes = quotes,
        quotes_usd = quotes_usd,
        values_usd = values_usd)

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    symbol = request.form.get("symbol")
    if request.method == 'POST':
        if not request.form.get("symbol"):
            return apology("No symbol typed")
        #use lookup, and if symbol is made up, aplogize
        quote = lookup(symbol)
        if quote == None:
            return apology("Invalid Symbol")
        return render_template("quoted.html",
        name =quote["name"], price=usd(quote["price"]), sym=quote["symbol"])
    return render_template("quote.html")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == 'POST':
        #set shares as shares and symbol and symbol
        shares = request.form.get("shares")
        try:
            shares = int(shares)
        except:
            ValueError
            return apology("Number of shares has to be an integer")     

        symbol = request.form.get("symbol").upper()
        #if no symbol then scold
        if not request.form.get("symbol"):
            return apology("Sorry what are you buying?")
        #use lookup, and if symbol is made up, aplogize
        quote = lookup(symbol)
        if quote == None:
            return apology("{} is not a real company".format(symbol))
        #just in case bad # of shares
        if shares <= 0:
            return apology("Sorry you can't buy this # of shares")
        #total amount of the purchase:
        cost = float(int(shares) * quote["price"])
        #locate the user transactions and transfer into a dict
        db.execute("SELECT cash FROM users WHERE id = :id", {"id": session["user_id"]})
        user_cash = list(db.fetchone())[0]

        #compare user amount with the cost
        leftover = float(user_cash - cost)
        if leftover >= 0:
            #put in the transaction, which is a general table for all users
            db.execute("INSERT INTO user_transaction('id', 'TransType', 'symbol', 'company', 'shares', 'share_price', 'total_transaction') VALUES(:id, :TransType, :symbol, :company, :shares, :share_price, :total_transaction)",
                {"id": session["user_id"], "TransType": "Bought", "symbol": symbol, "company": quote["name"], "shares": shares, "share_price": quote["price"], "total_transaction": cost})
            #put into total owned stocks of that user
            #first check if stock exists already
            db.execute("SELECT * FROM owned WHERE id = :id AND symbol = :symbol", {"id": session["user_id"], "symbol": symbol})
            exists = db.fetchone()
            #if doesn't exist, insert it in
            if not exists:
                db.execute("INSERT INTO owned VALUES(:id, :symbol, :shares)",
                {"id": session["user_id"], "symbol": symbol, "shares": shares})
                connection.commit()
            #if exists, update the number of shares
            else:
                db.execute("UPDATE owned SET shares= :shares WHERE id= :id AND symbol= :symbol",
                 {"shares": shares + exists[2], "id": session["user_id"], "symbol": symbol})
                connection.commit()
            #deduct the cash amount from the user
            db.execute("UPDATE users SET cash = :leftover WHERE id = :id", {"leftover": leftover, "id": session["user_id"]})
            connection.commit()
        #if the user's left over doesn't have enough
        else:
            #TODO ADD HOW MUCH SHORT
            return apology("sorry... you're broke")
    return render_template("buy.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == 'POST':
        #set shares as shares and symbol and symbol
        shares = request.form.get("shares")
        try:
            shares = int(shares)
        except:
            ValueError
            return apology("Number of shares has to be an integer") 
        symbol = request.form.get("symbol").upper()
        #if no symbol then scold
        if not request.form.get("symbol"):
            return apology("Sorry what are you selling?")
        #use lookup, and if symbol is made up, aplogize
        quote = lookup(symbol)
        if quote == None:
            return apology("{} is not a real company".format(symbol))
        #if no shares then scold
        if not request.form.get("shares"):
            return apology("Please enter number of shares you want to sell")

        #just in case bad # of shares
        if shares <= 0:
            return apology("Sorry you can't sell this # of shares")

        #see the number of shares the user has of the stock
        db.execute("SELECT shares FROM owned WHERE id = :id AND symbol = :symbol", {"id": session["user_id"], "symbol": symbol})
        user_shares = 0
        try:
            user_shares = int(db.fetchone()[0])
        except:
            ValueError
            return apology("sup you don't own this stock")

        #check if the user owns this many shares that was selected to sell. If yes, reduce owned # by chosen amount.
        if user_shares >= shares:
            db.execute("UPDATE owned SET shares = :shares WHERE id = :id AND symbol = :symbol", {"shares": user_shares-shares, "id": session["user_id"], "symbol": symbol})
            connection.commit()
        else:
            return apology("You don't own this many shares")
        
        #select from the user the amount of cash before transaction
        db.execute("SELECT cash FROM users WHERE id = :id", {"id": session["user_id"]})
        before = float(db.fetchone()[0])
        #total amount for the transaction
        profit = float(int(shares) * quote["price"])
        #total amount of user cash after the purchase:
        cash_after = float(before + profit)
        #update new cash amount after purchase
        db.execute("UPDATE users SET cash = :cash WHERE id = :id", {"cash": cash_after, "id": session["user_id"]})
        connection.commit()

        #if the user sold all of their shares of the stock, delete the column from owned
        db.execute("SELECT shares FROM owned WHERE id = :id AND symbol = :symbol", {"id": session["user_id"], "symbol":symbol})
        after = int(db.fetchone()[0])
        if after == 0:
            db.execute("DELETE FROM owned WHERE id = :id AND symbol = :symbol", {"id": session["user_id"], "symbol": symbol})
            connection.commit()

        #put transaction into user_transaction
        db.execute("INSERT INTO user_transaction('id', 'TransType', 'symbol', 'company', 'shares', 'share_price', 'total_transaction') VALUES(:id, :TransType, :symbol, :company, :shares, :share_price, :total_transaction)",
                {"id": session["user_id"], "TransType": "Sold", "symbol": symbol, "company": quote["name"], "shares": shares, "share_price": quote["price"], "total_transaction": profit})

    return render_template("sell.html")
        

@app.route("/register", methods=["GET", "POST"])
def register():
    # Forget any user_id
    session.clear()
    #get password data for turning into hash
    password = request.form.get("password")
    if request.method == 'POST':
        # insure username is submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)
        # insure password is submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        elif not request.form.get("confirm_password"):
            return apology("must confirm password", 403)
        # insure password are the same:
        elif request.form.get("password") != request.form.get("confirm_password"):
            return apology("password must match!", 403)
        # make password for user, and generate hash
        password = request.form.get("password")
        hash = generate_password_hash(password)
        # add user into database
        db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", {"username": request.form.get("username"), "hash": hash})
        # username=request.form.get("username"), hash=hash)
        connection.commit()
        return success()
    return render_template("register.html")

@app.route("/logout")
def logout():
    """Log user out"""
    # Forget any user_id
    session.clear()
    # Redirect user to login form
    return redirect("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    #username
    username = session["username"]
    #get the user cash amount
    db.execute("SELECT * FROM users WHERE id = :id", {"id": session["user_id"]})
    user_cash = db.fetchone()[0]
    #get the transactions information
    transactions = db.execute("SELECT * FROM user_transaction WHERE id = :id", {"id": session["user_id"]})
    transaction_key = ["id", "symbol", "shares", "total_transaction", "time", "company", "type", "share_price"]
    transaction_value = db.fetchall()
    transactions = []
    # make a list of dictionaries for the transactions
    for stock in range(len(transaction_value) - 1, 0, -1):
        current_stock = {}
        for key in range(len(transaction_value[stock])):
            current_stock[transaction_key[key]] = transaction_value[stock][key]
        transactions.append(current_stock)

    #gotta remember to add your dicts to render_template!
    return render_template("history.html",
        username=username,
        user_cash=usd(user_cash),
        transactions=transactions)

if __name__ == '__main__':
    # app.run(debug=True,host='0.0.0.0',port=int(os.environ.get('PORT', 8080)))
    app.run()
