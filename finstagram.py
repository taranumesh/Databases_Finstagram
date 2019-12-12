from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time
import hashlib

SALT = 'cs3083'

app = Flask(__name__)
app.secret_key = "super secret key"

IMAGES_DIR = os.path.join(os.getcwd(), "images")

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
    followerPhotos = "CREATE VIEW followerPhotos AS SELECT DISTINCT PhotoID, file, photoPoster, caption, postingDate FROM Photo JOIN Follow ON (PhotoPoster=username_followed) WHERE followstatus=true AND username_follower=%s AND allFollowers='true'"
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

    # Tagging: processing of query to select all posts the user has been tagged in to pass to home.html
    cursor = connection.cursor()
    query = "SELECT * FROM Photo WHERE EXISTS (SELECT photoID FROM Tagged WHERE username=%s AND tagstatus IS NULL AND Tagged.photoID=Photo.photoID)"
    cursor.execute(query, (user))
    images_tagged_data = cursor.fetchall()
    cursor.close()

    return render_template("home.html", username=session["username"], images=data, images_tagged=images_tagged_data,
                           message="")


# Tagging: route to manage input from "/tag" form in home.html
@app.route("/tag", methods=["POST"])
@login_required
def tag():
    requestData = request.form
    tagger = session["username"]
    tagged = requestData["username"]
    photoid_form = requestData["photoID"]

    cursor = connection.cursor()
    query = "SELECT username, tagstatus from Tagged WHERE photoID=%s"
    cursor.execute(query, (photoid_form))
    usernames = cursor.fetchall()
    cursor.close()

    # print(usernames[0]["username"])

    length_test = len(usernames)

    exists = False

    for i in range(length_test):
        print("in for loop usernames[i][username]:", usernames[i]["username"])
        print("in for loop tagged:", tagged)
        if (usernames[i]["username"] == tagged):  # person is already tagged and you want to go to elif
            exists = True

    if (tagged == tagger):  # self-tagging
        cursor = connection.cursor()
        query = "INSERT INTO Tagged (username, photoID, tagstatus) VALUES (%s, %s, true)"
        cursor.execute(query, (tagger, photoid_form))
        cursor.close()
        message = "You've successfuly tagged yourself"
    elif (exists):  # tagging someone already tagged or person hasn't accepted tag request
        message = "This person could not be tagged"
    else:  # not self-tagging
        cursor = connection.cursor()
        followerPhotos = "CREATE VIEW followerPhotos AS SELECT DISTINCT photoID, file, photoPoster, caption, postingDate FROM Photo JOIN Follow ON (PhotoPoster=username_followed) WHERE username_follower=%s AND allFollowers='true'"
        cursor.execute(followerPhotos, (tagged))
        cursor.close()

        # Get photos of person being tagged
        cursor = connection.cursor()
        myPhotos = "CREATE VIEW myPhotos AS SELECT photoID, file, photoPoster, caption, postingDate FROM Photo WHERE photoPoster=%s"
        cursor.execute(myPhotos, (tagged))
        cursor.close()

        # Get photos from the groups of person being tagged
        cursor = connection.cursor()
        groupPhotos = "CREATE VIEW groupPhotos AS SELECT DISTINCT photoID, file, photoPoster, caption, postingDate FROM Photo JOIN BelongTo as b1 ON (member_username = photoPoster) WHERE EXISTS (SELECT member_username FROM BelongTo WHERE groupName=b1.groupName AND member_username=%s)"
        cursor.execute(groupPhotos, (tagged))
        cursor.close()

        # Get all feed posts of person being tagged
        cursor = connection.cursor()
        query = "CREATE VIEW taggedFeed AS SELECT photoID FROM followerPhotos UNION (SELECT photoID FROM myPhotos) UNION (SELECT photoID FROM groupPhotos) ORDER BY photoID DESC"
        cursor.execute(query)
        photos = cursor.fetchall()
        cursor.close()

        # Select the photo the person is being tagged in
        cursor = connection.cursor()
        query = "SELECT * FROM taggedFeed WHERE photoID=%s"
        cursor.execute(query, (photoid_form))
        photo = cursor.fetchall()
        cursor.close()

        # Drop all views
        cursor = connection.cursor()
        query = "DROP VIEW followerPhotos, myPhotos, groupPhotos, taggedFeed"
        cursor.execute(query)
        cursor.close()

        if (photo == ()):  # If photo IS NOT viewable by person being tagged
            message = "User could not be tagged"
        else:  # If photo IS viewable by person being tagged, insert data into tagged
            cursor = connection.cursor()
            query = "INSERT INTO Tagged (username, photoID, tagstatus) VALUES (%s, %s, NULL)"
            cursor.execute(query, (tagged, photoid_form))
            cursor.close()
            message = "Tag request was successfuly sent to user"
            return render_template("tagresult.html", message=message)  # display message to user depending on result

    return render_template("tagresult.html", message=message)


# Tagging: route to manage tags (user can accept or deny being tagged in a photo)
# specifcally via /managetags form in home.html
@app.route("/managetags", methods=["POST"])
@login_required
def manage_tags():
    requestData = request.form
    username = session["username"]
    photoid_form = requestData["photoID"]
    response = requestData["allow"]

    if (response == "true"):  # if person accepts tag, update tagstatus value in Tagged table
        cursor = connection.cursor()
        query = "UPDATE Tagged SET tagstatus=true WHERE username=%s AND photoID=%s"
        cursor.execute(query, (username, photoid_form))
        connection.commit()
        cursor.close()
        message = "You'be been tagged!"
    else:  # if person denies tag, delete status request from Tagged table
        cursor = connection.cursor()
        query = "DELETE FROM Tagged WHERE username=%s AND photoID=%s"
        cursor.execute(query, (username, photoid_form))
        connection.commit()
        cursor.close()
        message = "You've denied being tagged from this photo"

    return render_template("manageTagsResult.html", message=message)  # display message to user depending on result


@app.route("/info", methods=["POST"])
@login_required
def photo_info():
    username = session["username"]
    requestData = request.form
    photoID_form = requestData["photoIDinfo"]
    photoPoster_form = requestData["photoPoster"]

    # getting photo info from Photo table ()
    cursor = connection.cursor()
    query = "SELECT * FROM Photo WHERE photoID=%s"
    cursor.execute(query, (photoID_form))
    get_photo = cursor.fetchone()
    cursor.close()

    # get first and last name of poster from Person table
    cursor = connection.cursor()
    query = "SELECT firstName, lastName FROM Person WHERE username=%s"
    cursor.execute(query, (photoPoster_form))
    get_names = cursor.fetchone()
    cursor.close()

    # get username and first/last name of people tagged
    # create view of people tagged
    cursor = connection.cursor()
    query = "CREATE VIEW taggedPeople AS SELECT username FROM Tagged WHERE photoID=%s AND tagstatus=true"
    cursor.execute(query, (photoID_form))
    cursor.close()
    # use username in taggedPeople table to get Person info
    cursor = connection.cursor()
    query = "SELECT * FROM Person WHERE EXISTS (SELECT username from taggedPeople WHERE taggedPeople.username=Person.username)"
    cursor.execute(query)
    get_tagged = cursor.fetchall()
    cursor.close

    # Drop all views
    cursor = connection.cursor()
    query = "DROP VIEW taggedPeople"
    cursor.execute(query)
    cursor.close()

    # get username and rating from Likes table of people who liked photo
    cursor = connection.cursor()
    query = "SELECT username, rating FROM Likes WHERE photoID=%s"
    cursor.execute(query, (photoID_form))
    get_likes = cursor.fetchall()
    cursor.close()

    return render_template("photoInfo.html", image=get_photo, names=get_names, tags=get_tagged, likes=get_likes)


@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("upload.html")


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
        # with open(filepath, 'rb') as file:
        # 	binaryData = file.read()
        caption = request.form["caption"]
        allfollowers = request.form["allFollowers"]
        photoPoster = session["username"]

        # Get the last posted PhotoID and increment
        cursor = connection.cursor()
        cursor.execute("SELECT MAX(photoID) FROM Photo")
        photoID_max = cursor.fetchall()
        if (photoID_max[0]["MAX(photoID)"] != None):
            photoID = photoID_max[0]["MAX(photoID)"] + 1
        else:
            photoID = 1;
        cursor.close()
        query = "INSERT INTO photo (photoID, postingDate, file, allFollowers, caption, photoPoster) VALUES (%s, %s, %s, %s, %s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(query, (
            photoID, time.strftime('%Y-%m-%d %H:%M:%S'), image_name, allfollowers, caption, photoPoster))
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
        userPhotos = "SELECT photoID, file, photoPoster, caption, postingDate FROM Photo WHERE photoPoster=%s AND allFollowers='true' ORDER BY postingDate DESC"
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
            message = "New Group " + groupname + " Added"
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
        group_exists = cursor.fetchone()
        cursor.close()
        # print("Group is "+group_exists)

        user = "SELECT * FROM Person WHERE username=%s"
        cursor = connection.cursor()
        cursor.execute(user, (adduser))
        user_exists = cursor.fetchone()
        cursor.close()
        # print("User is "+user_exists)

        user_already = "SELECT * FROM BelongTo WHERE member_username=%s AND groupName=%s"
        cursor = connection.cursor()
        cursor.execute(user_already, (adduser, groupname))
        user_already_group = cursor.fetchone()
        cursor.close()

        # print("User Already is "+user_already_group)

        if (group_exists is not None) and (user_exists is not None) and (user_already_group is None):
            message = "User " + adduser + " Added to " + groupname
            addUser = "INSERT INTO BelongTo (member_username, owner_username, groupName) VALUES (%s,%s,%s)"
            cursor = connection.cursor()
            cursor.execute(addUser, (adduser, username, groupname))
            cursor.close()
        else:
            if (user_already_group is not None):
                message = "User already in group"
            else:
                message = "Group or User Does Not Exist"
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
                if (user_follows == ()):
                    cursor = connection.cursor()
                    query = "INSERT INTO Follow (username_followed, username_follower, followstatus) VALUES (%s, %s, NULL)"
                    cursor.execute(query, (follow_user, username))
                    connection.commit()
                    cursor.close()
                    message = "Follow request sent to @" + follow_user
                else:
                    message = "Already following @" + follow_user
            elif (follow == "Unfollow"):
                cursor = connection.cursor()
                query = "DELETE FROM Follow WHERE username_followed=%s AND username_follower=%s"
                cursor.execute(query, (follow_user, username))
                connection.commit()
                cursor.close()
                message = "Unfollowed @" + follow_user
        else:
            message = "@" + follow_user + " not found"
    else:
        message = "Error!"
    return render_template("follow.html", message=message)


@app.route("/requests", methods=["GET"])
@login_required
def requests():
    # Get all follow requests
    cursor = connection.cursor()
    username = session["username"]
    query = "SELECT username_follower FROM Follow WHERE username_followed=%s AND followstatus IS NULL"
    cursor.execute(query, (username))
    data = cursor.fetchall()
    cursor = connection.cursor()
    cursor.close()

    return render_template("requests.html", requests=data, message="")


@app.route("/respondtorequest", methods=["POST"])
@login_required
def follow_request():
    response = request.form["followstatus"]
    followed = session["username"]
    follower = request.form["follower"]

    if (response == 'true'):
        query = "UPDATE Follow SET followstatus = 1 WHERE username_followed=%s AND username_follower=%s"
        cursor = connection.cursor()
        cursor.execute(query, (followed, follower))
        connection.commit()
        cursor.close()
        message = "You have accepted @" + follower + "'s follow request"
    elif (response == 'false'):
        query = "DELETE FROM Follow WHERE username_followed=%s AND username_follower=%s"
        cursor = connection.cursor()
        cursor.execute(query, (followed, follower))
        connection.commit()
        cursor.close()
        message = "You have denied @" + follower + "'s follow request"

    return render_template("requestsresponse.html", message=message)


@app.route("/comment", methods=["POST"])
@login_required
def comment():
    if request.form:
        cursor = connection.cursor()
        commenter = session["username"]
        photoID = request.form.get("photoID")
        commentText = request.form.get("text")
        query = 'INSERT INTO Comment(username, photoID, commentText) VALUES(%s, %s, %s)'
        cursor.execute(query, (commenter, photoID, commentText))
        connection.commit()
        cursor.close()
    return render_template("photoInfo.html")


@app.route("/like", methods=["POST"])
@login_required
def like():
    if request.form:
        cursor = connection.cursor()
        username = session["username"]
        photoID = request.form.get("photoID")
        query = "SELECT * FROM Likes WHERE username=%s AND photoID=%s"
        cursor.execute(query, (username, photoID))
        data = cursor.fetchone()
        cursor.close()
        if data:
            message = "You've already liked this photo"
        else:
            message = "You liked the photo"
            newLike = 'INSERT INTO Likes(username, photoID, liketime, rating) VALUES(%s, %s, %s, NULL)'
            cursor = connection.cursor()
            cursor.execute(newLike, (username, photoID, time.strftime('%Y-%m-%d %H:%M:%S')))
            cursor.close()

    else:
        message = "Error occurred liking photo"
    return render_template("photoInfo.html", message=message)


if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run()