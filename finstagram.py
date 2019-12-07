from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time
import hashlib

SALT = 'cs3083'

#***
# UPLOAD_FOLDER = '/Users/dannyalcedo/PycharmProjects/finstagram/uploads'
# ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
#**

app = Flask(__name__)
app.secret_key = "super secret key"

#***
IMAGES_DIR = os.path.join(os.getcwd(), "images")
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
#***

connection = pymysql.connect(host="localhost",
                             user="root",
                             password="root",
                             db="finstagram",
                             charset="utf8mb4",
                             port=8889,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/home")
@login_required
def home():
    user = session["username"]
    
    # Get photos from people you follow
    cursor = connection.cursor()
    followerPhotos = "CREATE VIEW followerPhotos AS SELECT DISTINCT PhotoID, file, photoPoster, caption, postingDate FROM Photo JOIN Follow ON (PhotoPoster=username_followed) WHERE username_follower=%s AND allFollowers='true'"
    cursor.execute(followerPhotos, (user))
    cursor.close()

    # Get your own photos
    cursor = connection.cursor()
    myPhotos = "CREATE VIEW myPhotos AS SELECT PhotoID, file, photoPoster, caption, postingDate FROM Photo WHERE photoPoster=%s"
    cursor.execute(myPhotos, (user))
    cursor.close()

    # Get photos from the group
    cursor = connection.cursor()
    groupPhotos = "CREATE VIEW groupPhotos AS SELECT DISTINCT PhotoID, file, photoPoster, caption, postingDate FROM Photo JOIN BelongTo as b1 ON (member_username = photoPoster) WHERE EXISTS (SELECT member_username FROM BelongTo WHERE groupName=b1.groupName AND member_username=%s)"
    cursor.execute(groupPhotos, (user))
    cursor.close()

    # Get all feed posts
    cursor = connection.cursor()
    feed = "SELECT DISTINCT * FROM followerPhotos UNION (SELECT * FROM myPhotos) UNION (SELECT * FROM groupPhotos) ORDER BY postingDate DESC"
    cursor.execute(feed)
    data = cursor.fetchall()
    cursor = connection.cursor()

    # Drop all views
    cursor = connection.cursor()
    query = "DROP VIEW followerPhotos, myPhotos, groupPhotos"
    cursor.execute(query)
    cursor.close()
    return render_template("home.html", username=session["username"], images=data, message="")

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("upload.html")

# @app.route("/images", methods=["GET"])
# @login_required
# def images():
	# user = session["username"]
	# cursor = connection.cursor()
	# followerPhotos = "CREATE VIEW follower_photos AS SELECT photoID, photoPoster FROM Photo JOIN Follow ON (PhotoPoster=username_followed) WHERE username_follower=%s AND allFollowers=1 ORDER BY timestamp DESC"
	# cursor.execute(followerPhotos, (user))
	# data = cursor.fetchall()
	# cursor.close()

	# cursor.conn.cursor()
	# dropview = "DROP VIEW follower_photos"
	# cursor.execute(dropview)
	# cursor.close()

	# return render_template("images.html", images=data)
    # query = "SELECT * FROM photo"
    # with connection.cursor() as cursor:
    #     cursor.execute(query)
    # data = cursor.fetchall()

@app.route("/image/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        password = requestData["password"] + SALT
        hashedPassword = hashlib.sha256(password.encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)
    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)

@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        password = requestData["password"] + SALT
        hashedPassword = hashlib.sha256(password.encode("utf-8")).hexdigest()
        firstName = requestData["firstName"]
        lastName = requestData["lastName"]
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, firstName, lastName) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName))
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (username)
            return render_template('register.html', error=error)    
        print("sucess")
        return redirect(url_for("login"))
    print("fail")
    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

@app.route("/uploadImage", methods=["POST"])
@login_required
def upload_image():
    if request.files:
        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        print(filepath)
        with open(filepath, 'rb') as file:
        	binaryData = file.read()
        caption = request.form["caption"]
        allfollowers = request.form["allFollowers"]
        photoPoster = session["username"]
        # Get the last posted PhotoID and increment
        cursor = connection.cursor()
        cursor.execute("SELECT MAX(PhotoID) FROM Photo")
        photoID_max = cursor.fetchall()
        if (photoID_max[0]["MAX(PhotoID)"] != ()):
            photoID = photoID_max[0]["MAX(PhotoID)"] + 1
        else:
            photoID = 1;
        cursor.close()
        query = "INSERT INTO photo (PhotoID, postingDate, file, allFollowers, caption, photoPoster) VALUES (%s, %s, %s, %s, %s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(query, (photoID, time.strftime('%Y-%m-%d %H:%M:%S'), binaryData, allfollowers, caption, photoPoster))
        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message)

    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message)

@app.route("/search", methods=["POST"])
@login_required
def search_user():
    if request.form:
        requestData = request.form
        username = requestData["searchbar"]
        cursor = connection.cursor()
        userPhotos = "SELECT PhotoID, file, photoPoster, caption, postingDate FROM Photo WHERE photoPoster=%s AND allFollowers='true' ORDER BY postingDate DESC"
        cursor.execute(userPhotos, (username))
        data = cursor.fetchall()
        cursor.close()
        if (data == ()):
            message = "No posts found from username: @" + username
        else:
            message = "@" + username + " Posts"
        return render_template("search.html", images=data, message=message)
    else:
        return render_template("search.html", message="Error")

@app.route("/groups", methods=["GET"])
@login_required
def groups():
    return render_template("groups.html")

@app.route("/creategroup", methods=["POST"])
@login_required
def create_group():
    if request.form:
        requestData = request.form
        username = session["username"]
        groupname = requestData["groupname"]
        description = requestData["description"]
        group = "SELECT * FROM FriendGroup WHERE groupName=%s AND groupOwner=%s"
        cursor = connection.cursor()
        cursor.execute(group, (groupname, username))
        data = cursor.fetchone()
        cursor.close()
        if data:
            message = "Group Already Exists"
        else:
            message = "New Group "+groupname+" Added"
            addGroup = "INSERT INTO FriendGroup (groupOwner, groupName, description) VALUES (%s,%s,%s)"
            cursor = connection.cursor()
            cursor.execute(addGroup, (username, groupname, description))
            cursor.close()
            addGroup = "INSERT INTO BelongTo (member_username, owner_username, groupName) VALUES (%s,%s,%s)"
            cursor = connection.cursor()
            cursor.execute(addGroup, (username, username, groupname))
            cursor.close()
    else:
        mesage = "Error occured creating group."
    return render_template("groups.html", message=message)

@app.route("/addgroupmember", methods=["POST"])
@login_required
def add_user():
    if request.form:
        requestData = request.form
        username = session["username"]
        groupname = requestData["groupname"]
        adduser = requestData["adduser"]
        group = "SELECT * FROM FriendGroup WHERE groupName=%s AND groupOwner=%s"
        cursor = connection.cursor()
        cursor.execute(group, (groupname, username))
        data = cursor.fetchone()
        cursor.close()
        if data:
            message = "User "+adduser+" Added to "+groupname
            addUser = "INSERT INTO BelongTo (member_username, owner_username, groupName) VALUES (%s,%s,%s)"
            cursor = connection.cursor()
            cursor.execute(addUser, (adduser, username, groupname))
            cursor.close()
        else:
            message = "Group Does Not Exist"
    else:
        mesage = "Error occured creating group."
    return render_template("groups.html", message=message)
@app.route("/follow", methods=["POST"])
@login_required
def follow_unfollow():
    if request.form:
        requestData = request.form
        username = session["username"]
        follow_user = requestData["followuser"]
        follow = requestData["follow"]
        cursor = connection.cursor()
        query = "SELECT * FROM Person WHERE username=%s"
        cursor.execute(query, (follow_user))
        user_exists = cursor.fetchall()
        cursor.close()
        if (user_exists != ()):
            if (follow == "Follow"):
                cursor = connection.cursor()
                query = "SELECT * FROM Follow WHERE username_followed=%s AND username_follower=%s"
                cursor.execute(query, (follow_user, username))
                user_follows = cursor.fetchall()
                cursor.close()
                print(user_follows)
                if (user_follows==()):
                    cursor = connection.cursor()
                    query = "INSERT INTO Follow (username_followed, username_follower, followstatus) VALUES (%s, %s, 1)"
                    cursor.execute(query, (follow_user, username))
                    cursor.close()
                    message = "Followed @"+follow_user
                else:
                    message = "Already following @"+follow_user
            elif (follow == "Unfollow"):
                cursor = connection.cursor()
                query = "DELETE FROM Follow WHERE username_followed=%s AND username_follower=%s"
                cursor.execute(query, (follow_user, username))
                cursor.close()
                message = "Unfollowed @"+follow_user
        else:
            message = "@"+follow_user+" not found"
    else:
        message = "Error!"
    return render_template("follow.html", message=message)

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run()
