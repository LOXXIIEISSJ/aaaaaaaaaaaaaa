print("Loading...")
import tools
from os import environ
from threading import Thread

from flask import Flask, render_template, redirect, url_for, request, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

print("Importing 1/2")
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, SubmitField, TextAreaField, FileField, SelectField
from wtforms.validators import Length, Regexp
from flask_wtf.file import FileAllowed
from flask_admin import Admin
from flaskext.markdown import Markdown
from flask_admin.contrib.sqla import ModelView
from bleach import clean
from werkzeug.security import generate_password_hash, check_password_hash

print("Importing 2/2")
from werkzeug.utils import secure_filename
from waitress import serve
from flask_talisman import Talisman
from flask_ipban import IpBan
from jwt import encode, decode
from PIL import Image
from flask_migrate import Migrate
from flask_compress import Compress

print("Finished importing...")

app_settings = tools.GetSettings()

app = Flask('app')
app.config['SECRET_KEY'] = environ['secret']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///main.db'
app.config['MAX_CONTENT_LENGTH'] = 57476300

from sqlalchemy import MetaData
metadata = MetaData(
    naming_convention={
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
    }
)

db = SQLAlchemy(app, metadata=metadata)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
app.config['FLASK_ADMIN_SWATCH'] = 'cerulean'
admin = Admin(app)
Markdown(app)
talisman = Talisman(app, content_security_policy={'img-src': '*', 'object-src': [], 'script-src': []})
migrate = Migrate(app, db, render_as_batch=True)
ip_ban = IpBan(app)
compress = Compress(app)

ip_ban.load_nuisances()


class LoginForm(FlaskForm):
  username = StringField('Username', validators=[Length(min=3, max=80)])
  password = PasswordField('Password', validators=[Length(min=5, max=600)])
  submitLogin = SubmitField('Login')


class RegisterForm(FlaskForm):
  username = StringField(
    'Username', validators=[Length(min=3, max=80),
                            Regexp(r'^[\w.@+-]+$')])
  email = EmailField('Email', validators=[Length(max=60)])
  password = PasswordField('Password', validators=[Length(min=5, max=600)])
  submitReg = SubmitField('Register')


class CreatePostForm(FlaskForm):
  title = StringField('Title', validators=[Length(min=5, max=200)])
  content = TextAreaField('Content', validators=[Length(min=10, max=3000)])
  submitCreate = SubmitField('Publish')
  tags = SelectField('Tags')


class CommentForm(FlaskForm):
  content = TextAreaField('Reply', validators=[Length(min=5, max=3000)])
  submitReply = SubmitField('Reply')


class SettingsForm(FlaskForm):
  profile_pic = FileField(
    'Profile', validators=[FileAllowed(['jpg', 'png', 'gif'], 'Images only!')])
  description = TextAreaField('Desc', validators=[Length(max=500)])
  password = PasswordField('Password', validators=[Length(min=5, max=600)])
  newPassword = PasswordField('New Password', validators=[Length(min=5, max=600)])
  delete = StringField('Delete')
  submitSettings = SubmitField('Change')
  resendConf = SubmitField('Resend')


class ModifyPostForm(FlaskForm):
  deletePost = SubmitField('delete')
  deleteComment = SubmitField('delete')


class OAUTHForm(FlaskForm):
  agree = SubmitField('Authorize')

class EditPostForm(FlaskForm):
  newTitle = StringField('Title', validators=[Length(min=5, max=200)])
  newContent = TextAreaField('New Content', validators=[Length(max=3000)])
  submitEdit = SubmitField('Save')


class FollowForm(FlaskForm):
  submit = SubmitField('follow')


class LikeForm(FlaskForm):
  like = SubmitField('like')
  dislike = SubmitField('dislike')
  likeComment = SubmitField('like comment')
  dislikeComment = SubmitField('dislike comment')


class DeleteCommentForm(FlaskForm):
  deleteComment = SubmitField('delete')


followers = db.Table(
  'followers', db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
  db.Column('followed_id', db.Integer, db.ForeignKey('user.id')))


class User(UserMixin, db.Model):
  id = db.Column(db.Integer, primary_key=True)
  username = db.Column(db.String(80), nullable=False, unique=True)
  description = db.Column(db.String(500), nullable=True)
  email = db.Column(db.String(60), nullable=True, unique=True)
  password = db.Column(db.String(600), nullable=False)
  confirmed = db.Column(db.Boolean(), nullable=False, default=False)
  registered_on = db.Column(db.DateTime,
                            nullable=False,
                            default=datetime.utcnow)
  profile_pic = db.Column(db.String(), default="default.png")
  role = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
  roledata = db.relationship(lambda: Role,
                           uselist=False,
                           overlaps='user,role',
                           viewonly=True)
  admin = db.Column(db.Boolean(), nullable=False, default=False)
  posts = db.relationship('Post', backref='user', lazy=True)
  comments = db.relationship('Comment', backref='user', lazy=True)
  elo = db.Column(db.Integer, default=0)

  following = db.relationship('User',
                              secondary=followers,
                              backref=db.backref('followers', lazy='dynamic'),
                              primaryjoin=(followers.c.follower_id == id),
                              secondaryjoin=(followers.c.followed_id == id),
                              lazy='dynamic')
  notifications = db.relationship('Notification', backref='user', lazy=True)
  last_active = db.Column(db.DateTime,
                            nullable=True,
                            default=datetime.utcnow)
  liked = db.relationship(
    'ContentVote',
    foreign_keys='ContentVote.user_id',
    backref='user', lazy='dynamic')

  def getNewNotifications(self):
    return [n for n in self.notifications if n.read==False]

  def likedPost(self, post):
    data = ContentVote.query.filter_by(
      user_id = self.id,
      post_id = post.id
    ).first()
    if data == None: return None
    return data.isLike

  def likedComment(self, comment):
    data = ContentVote.query.filter_by(
      user_id = self.id,
      comment_id = comment.id
    ).first()
    if data == None: return None
    return data.isLike
  
  def follow(self, other):
    if (other == self): return
    if self.isfollowing(other):
      self.following.remove(other)
    else:
      self.following.append(other)
    db.session.commit()

  def isfollowing(self, other):
    return self.following.filter(
      followers.c.followed_id == other.id).count() > 0

  def __repr__(self) -> str:
    return self.username

class Role(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  role_name = db.Column(db.String(150))
  color = db.Column(db.String(8)) #XxXxXx
  users = db.relationship('User', backref='post', lazy=True)

  def __repr__(self) -> str:
    return self.role_name
  

class Post(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  title = db.Column(db.String(200), nullable=False)
  content = db.Column(db.String(3000), nullable=False)
  author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
  author = db.relationship(lambda: User,
                           uselist=False,
                           overlaps='post,user',
                           viewonly=True)
  created_on = db.Column(db.DateTime,
                         nullable=False,
                         default=datetime.utcnow,
                         index=True)
  replies = db.relationship('Comment', backref='post', lazy=True)
  msubtopic = db.Column(db.Integer,
                        db.ForeignKey('subtopic.id'),
                        nullable=False)
  sub = db.relationship(lambda: Subtopic,
                        uselist=False,
                        overlaps='post,subtopic',
                        viewonly=True)
  uuid = db.Column(db.String(40), default=tools.CreateUUID())
  mtag = db.Column(db.Integer, db.ForeignKey('tags.id'), nullable=True)
  tag = db.relationship(lambda: Tags,
                        uselist=False,
                        overlaps='post,tags',
                        viewonly=True)
  anon = db.Column(db.Boolean(), nullable=False, default=False)
  edited_time = db.Column(db.DateTime,
                         nullable=True)
  votes = db.relationship('ContentVote', backref='post', lazy=True)

  def getLikes(self):
    return len([vote for vote in self.votes if vote.isLike])

  def getDislikes(self):
    return len(self.votes) - self.getLikes()
  
  def like(self, user: User):
    likeData = user.likedPost(self)
    if likeData == False:
      db.session.delete(ContentVote.query.filter_by(user_id = user.id,post_id = self.id).first())
    if likeData != True:
      cv = ContentVote(user_id=user.id, post_id=self.id, isLike=True, isPost=True)
      db.session.add(cv)
      db.session.commit()
    else:
      c = ContentVote.query.filter_by(user_id = user.id,post_id = self.id).first()
      db.session.delete(c)

  def dislike(self, user: User):
    likeData = user.likedPost(self)
    if likeData == True:
      db.session.delete(ContentVote.query.filter_by(user_id = user.id,post_id = self.id).first())
    if likeData != False:
      cv = ContentVote(user_id=user.id, post_id=self.id, isLike=False, isPost=True)
      db.session.add(cv)
      db.session.commit()
    elif likeData == False:
      db.session.delete(ContentVote.query.filter_by(user_id = user.id,post_id = self.id).first())


class Comment(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  content = db.Column(db.String(3000), nullable=False)
  author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
  author = db.relationship(lambda: User,
                           uselist=False,
                           overlaps='comment,user',
                           viewonly=True)
  reply_to_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
  created_on = db.Column(db.DateTime,
                         nullable=False,
                         index=True,
                         default=datetime.utcnow)
  
  votes = db.relationship('ContentVote', backref='comment', lazy=True)
  def getLikes(self):
    return len([vote for vote in self.votes if vote.isLike])

  def getDislikes(self):
    return len(self.votes) - self.getLikes()

  def like(self, user: User):
    likeData = user.likedComment(self)
    if likeData == False:
      db.session.delete(ContentVote.query.filter_by(user_id = user.id,comment_id = self.id).first())
    if likeData != True:
      cv = ContentVote(user_id=user.id, comment_id=self.id, isLike=True, isPost=False)
      db.session.add(cv)
      db.session.commit()
    else:
      c = ContentVote.query.filter_by(user_id = user.id,comment_id = self.id).first()
      db.session.delete(c)

  def dislike(self, user: User):
    likeData = user.likedComment(self)
    if likeData == True:
      db.session.delete(ContentVote.query.filter_by(user_id = user.id,comment_id = self.id).first())
    if likeData != False:
      cv = ContentVote(user_id=user.id, comment_id=self.id, isLike=False, isPost=False)
      db.session.add(cv)
      db.session.commit()
    elif likeData == False:
      db.session.delete(ContentVote.query.filter_by(user_id = user.id,comment_id = self.id).first())

class ContentVote(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
  post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
  comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
  isLike = db.Column(db.Boolean(), nullable=False, default=False)
  isPost = db.Column(db.Boolean(), nullable=False, default=False)
  


class Email(db.Model):
  email = db.Column(db.String(60),
                    nullable=True,
                    unique=True,
                    primary_key=True)


class Notification(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  name = db.Column(db.String(200), nullable=False)
  m_user = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
  end_url = db.Column(db.String(200), nullable=False)
  read = db.Column(db.Boolean(), nullable=False, default=False)
  time = db.Column(db.DateTime,
                   nullable=False,
                   default=datetime.utcnow,
                   index=True)

  def __repr__(self) -> str:
    return self.name


class Topic(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  name = db.Column(db.String(200), nullable=False)
  subtopics = db.relationship('Subtopic', backref='topic', lazy=True)

  def __repr__(self) -> str:
    return self.name

class Subtopic(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  name = db.Column(db.String(200), nullable=False)
  m_url = db.Column(db.String(60), unique=True, nullable=False)
  posts = db.relationship('Post', backref='subtopic', lazy=True)
  m_topic = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
  adminTopic = db.Column(db.Boolean(), nullable=False, default=False)

  def __repr__(self) -> str:
    return self.name


class Tags(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  name = db.Column(db.String(200), nullable=False)
  posts = db.relationship('Post', backref='tags', lazy=True)
  admin_only = db.Column(db.Boolean(), nullable=False, default=False)

  def __repr__(self) -> str:
    return self.name


class adminView(ModelView):

  def is_accessible(self):
    if current_user.is_authenticated:
      return current_user.admin
    return False

  def inaccessible_callback(self, name, **kwargs):
    return redirect(url_for(
      'login', next=request.url))  # vunerable to phishing attacks :/


admin.add_view(adminView(User, db.session))
admin.add_view(adminView(Post, db.session))
admin.add_view(adminView(Comment, db.session))
admin.add_view(adminView(Topic, db.session))
admin.add_view(adminView(Subtopic, db.session))
admin.add_view(adminView(Tags, db.session))
admin.add_view(adminView(Email, db.session))
admin.add_view(adminView(Notification, db.session))
admin.add_view(adminView(Role, db.session))

@login_manager.user_loader
def load_user(user_id):
  return User.query.get(int(user_id))

def getStats():
  pass


def CreateUser(username, email, password):
  default_role = Role.query.filter_by(color='grey').first()
  newUser = User(username=username,
                 email=email,
                 password=generate_password_hash(password, method='sha256'),
                 role=default_role.id)
  db.session.add(newUser)
  db.session.commit()
  return newUser


def CreatePost(title, content, author_id, subtopic: Subtopic, mtag: Tags):
  post = Post(
    title=clean(title),
    content=clean(content),
    author_id=author_id,
    msubtopic=subtopic.id,
    uuid=tools.CreateUUID(),
    mtag=Tags.query.filter_by(name=clean(mtag)).first_or_404().id)
  db.session.add(post)
  db.session.commit()
  return post


def CreateComment(content, author_id, reply_to_id):
  repid = Post.query.filter_by(uuid=reply_to_id).first_or_404().id
  comment = Comment(content=clean(content), author_id=author_id, reply_to_id=repid)
  db.session.add(comment)
  db.session.commit()


def DeleteComment(comment):
  db.session.delete(comment)
  db.session.commit()


def ConfirmUser(m_user):
  if m_user.confirmed:
    ip_ban.add()
    return

  m_user.confirmed = True
  db.session.add(Email(email=m_user.email))
  m_user.email = tools.CreateUUID()
  db.session.commit()


def DeletePost(m_post):
  m_post.anon = True
  db.session.commit()

def EditPost(m_post, title, content):
  m_post.title = clean(title)
  m_post.content = clean(content)
  m_post.edited_time = datetime.utcnow()
  db.session.commit()

def PushNotification(user, content, url):
  notification = Notification(m_user=user.id, name=content, end_url=url)
  db.session.add(notification)
  db.session.commit()
  return notification


import time
currently_online = []
newest_threads = []
def validate_online():
  global currently_online
  global newest_threads
  with app.app_context():
    while True:
      newest_threads = Post.query.order_by(Post.id.desc()).limit(6).all()
      currently_online = [user for user in currently_online if 6 > ((datetime.utcnow() - user.last_active).total_seconds() / 60)] 
      time.sleep(15)


class UserData:
  def __init__(self, username, last_active):
    self.username = username
    self.last_active = last_active

def appendOnline(udata: UserData):
  global currently_online
  for i in currently_online: 
    if i.username == udata.username: return
  currently_online.append(UserData(udata.username, udata.last_active))

def getOnline():
  global currently_online
  return currently_online

def getNewThreads():
  global newest_threads
  return newest_threads

@app.before_request
def updateLastActive():
  if not current_user.is_authenticated: return
  global currently_online
  current_user.last_active = datetime.utcnow()
  
  appendOnline(current_user)
  db.session.commit()

@app.route('/')
def index():
  return render_template("index.html")

@app.route('/thread/<id>', methods=['GET', 'POST'])
def thread(id):
  post = Post.query.filter_by(uuid=id).first_or_404()
  comment_form = CommentForm()
  modify_form = ModifyPostForm()
  follow_form = FollowForm()
  edit_form = EditPostForm()
  delete_comment_form = DeleteCommentForm()
  vote_form = LikeForm()

  page = request.args.get('page', 1, type=int)
  replies = Comment.query.filter_by(reply_to_id=post.id).paginate(
    page=page, per_page=5, error_out=True)

  if current_user.is_authenticated:
    if request.method == 'GET':
      if current_user == post.author:
        edit_form.newTitle.data = post.title
        edit_form.newContent.data = post.content
  
    if comment_form.submitReply.data and comment_form.validate():
      CreateComment(content=comment_form.content.data,
                    author_id=current_user.id,
                    reply_to_id=id)
      return redirect(url_for('thread', id=id))

    elif modify_form.deletePost.data and modify_form.validate():
      url = url_for('topic', murl=post.sub.m_url)
      DeletePost(post)
      return redirect(url)

    elif follow_form.submit.data and follow_form.validate():
      fuser = User.query.filter_by(
        id=request.form.get('follow_uid')).first_or_404()
      current_user.follow(fuser)
      PushNotification(
        user=current_user,
        content=
        f"You have just {'un' if not current_user.isfollowing(fuser) else ''}followed {fuser.username}!",
        url=url_for('thread', id=id, _external=True))
      PushNotification(
        user=fuser,
        content=current_user.username +
        f" has just {'un' if not current_user.isfollowing(fuser) else ''}followed you!",
        url=url_for('thread', id=id, _external=True))

    elif vote_form.like.data and vote_form.validate():
      post.like(current_user)
    
    elif vote_form.dislike.data and vote_form.validate():
      post.dislike(current_user)

    elif vote_form.likeComment.data and vote_form.validate():
      cid = request.form.get('comment_id')
      comment = Comment.query.filter_by(id=cid).first_or_404()
      comment.like(current_user)

    elif vote_form.dislikeComment.data and vote_form.validate():
      cid = request.form.get('comment_id')
      comment = Comment.query.filter_by(id=cid).first_or_404()
      comment.dislike(current_user)
    
    
    elif delete_comment_form.deleteComment.data and delete_comment_form.validate():
      replytodel = Comment.query.filter_by(id=request.form.get('deleteID')).first_or_404()
      if current_user == replytodel.author:
        DeleteComment(replytodel)
      redirect(url_for('thread', id=id))

    elif edit_form.validate_on_submit():
      EditPost(m_post=post, title=edit_form.newTitle.data, content=edit_form.newContent.data)
      return redirect(url_for('thread', id=id))

  return render_template("thread.html",
                         post=post,
                         comment_form=comment_form,
                         replies=replies,
                         modify_form=modify_form,
                         follow_form=follow_form,
                         edit_form=edit_form,
                         dcf=delete_comment_form,
                         vote_form=vote_form)

@app.route('/thread/<id>/<cid>', methods=['POST'])
@login_required
def vote(id, cid):
  like = request.args.get('vote', 1, type=bool)
  return f'voting for {cid} on {id}: liking={like}'

@app.route('/sub/<murl>/create', methods=['GET', 'POST'])
@login_required
def create(murl):
  sub = Subtopic.query.filter_by(m_url=murl).first_or_404()
  if sub.adminTopic == True and current_user.admin == False:
    abort(403)

  create_form = CreatePostForm()
  create_form.tags.choices = Tags.query.all(
  ) if current_user.admin == True else Tags.query.filter_by(
    admin_only=False).all()

  if create_form.validate_on_submit():
    post = CreatePost(title=create_form.title.data,
                      content=create_form.content.data,
                      author_id=current_user.id,
                      subtopic=sub,
                      mtag=create_form.tags.data)
    return redirect(url_for('thread', id=post.uuid))
  return render_template("create.html", form=create_form)

@app.route('/login', methods=['GET', 'POST'])
def login():
  login_form = LoginForm()
  register_form = RegisterForm()

  if login_form.submitLogin.data and login_form.validate():
    user = User.query.filter_by(username=login_form.username.data).first()
    if user and check_password_hash(user.password, login_form.password.data):
      login_user(user)
      next = request.args.get('next', type=str)
      if next:
        return redirect(next)
      return redirect(url_for("index"))
    else:
      return render_template("login.html",
                         login_form=login_form,
                         register_form=register_form,
                         error="Invalid username or password.")
      ip_ban.add()

  elif register_form.submitReg.data and register_form.validate():
    email = clean(register_form.email.data)
    is_valid = True # validate_email(email_address=email, check_regex=True, check_mx=True, smtp_timeout=10, dns_timeout=10, use_blacklist=True, debug=False)
    if Email.query.filter_by(email=email).first() or User.query.filter_by(username=register_form.username.data).first():
      return render_template("login.html",
                         login_form=login_form,
                         register_form=register_form,
                         error="Username or Email in use.")
    elif not is_valid:
      return render_template("login.html",
                         login_form=login_form,
                         register_form=register_form,
                         error="Invalid email.")
    else:
      tools.sendEmail(
        email,
        render_template('confirm.html',
                        expiry="[next server restart]",
                        code=encode({"email": email},
                                    app.config["SECRET_KEY"],
                                    algorithm="HS256"),
                        name=clean(register_form.username.data)),
        f"{app_settings['email']['shortname']} User Confirmation")
      
      user = CreateUser(
        username=clean(register_form.username.data),
        email=clean(register_form.email.data),
        password=register_form.password.data,
      )
      login_user(user)
    return redirect(url_for("index"))

  return render_template("login.html",
                         login_form=login_form,
                         register_form=register_form)


@app.route('/serve')
def mserve():
  topics = Topic.query.limit(5).all()
  return render_template("serve.html", topics=topics)

@app.route('/notifications')
@login_required
def notifications():
  page = request.args.get('page', 1, type=int)
  notifics = Notification.query.order_by(Notification.time.desc()).filter_by(m_user=current_user.id).paginate(page=page, per_page=30, error_out=True)
  for n in notifics:
    n.read = True
  db.session.commit()
  return render_template("notifications.html", notifications=notifics)

import os


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
  settings_form = SettingsForm()
  cuser = current_user
  user = User.query.filter_by(username=cuser.username).first()
  if request.method == 'GET':
    settings_form.description.data = user.description

  if settings_form.validate_on_submit() and check_password_hash(
      user.password, settings_form.password.data):

    if settings_form.delete.data[::-1] == current_user.username:
      current_user.delete()
      db.session.commit()

    if settings_form.newPassword.data:
      current_user.password = generate_password_hash(settings_form.newPassword.data, method='sha256')
      
    if settings_form.profile_pic.data:
      static_path = 'static/imgs/user/'
      if os.path.exists(static_path + current_user.profile_pic):
        os.remove(static_path + current_user.profile_pic)

      path = current_user.username + secure_filename(
        settings_form.profile_pic.data.filename)
      settings_form.profile_pic.data.save(static_path + path)
      im = Image.open(static_path + path)
      if im.format != 'GIF':
        im.thumbnail((400, 400))
        im.save(static_path + path)
        
      user.profile_pic = path

    user.description = clean(settings_form.description.data)
    if settings_form.resendConf.data:
      tools.sendEmail(
        user.email,
        render_template('confirm.html',
                        expiry="[next server restart]",
                        code=encode({"email": user.email},
                                    app.config["SECRET_KEY"],
                                    algorithm="HS256"),
                        name=user.username),
        f"{app_settings['email']['shortname']} User Confirmation")

    db.session.commit()
  elif request.method == "POST" and not check_password_hash(
      user.password, settings_form.password.data):
    ip_ban.add()

  return render_template("settings.html",
                         settings_form=settings_form,
                         cuser=cuser)


@app.route('/sub/<murl>')
def topic(murl):
  page = request.args.get('page', 1, type=int)
  sub = Subtopic.query.filter_by(m_url=murl).first_or_404()
  posts = Post.query.order_by(Post.created_on.desc()).filter_by(
    msubtopic=sub.id).paginate(page=page, per_page=10, error_out=False)
  return render_template("topic.html", sub=sub, posts=posts)


@app.route("/profile/", defaults={'username': None})
@app.route("/profile/<username>", methods=['GET', 'POST'])
def profile(username):
  user = None
  if username:
    user = User.query.filter_by(username=username).first_or_404()
  elif current_user.is_authenticated:
    user = User.query.filter_by(username=current_user.username).first_or_404()
  else:
    user = User.query.get(1)
    
  follow_form = FollowForm()

  if current_user.is_authenticated and follow_form.validate_on_submit():
    current_user.follow(user)

  posts = [post for post in user.posts if not post.anon]
  return render_template('profile.html', user=user, follow_form=follow_form, posts=posts)


@app.route("/confirm/<id>")
@login_required
def confirm(id):
  user = User.query.filter_by(email=current_user.email).first()
  try:
    if decode(id, app.config["SECRET_KEY"],
              algorithms="HS256")['email'] == current_user.email:
      ConfirmUser(user)
  except:
    abort(403)

  return redirect(url_for("index"))


@app.route("/logout")
@login_required
def logout():
  logout_user()
  return redirect(url_for("index"))


@app.route("/ipconfig")
@login_required
def ipconfig():
  if not current_user.admin:
    abort(403)

  return render_template('ipconfig.html',
                         items=ip_ban.get_block_list().items())

@app.route("/robots.txt")
def robots():
  return render_template('robots.txt')


@app.route("/legal")
def legal():
  return render_template('legal.html')

with app.app_context():
  db.create_all()
  if len(Role.query.filter_by(color='grey').all()) == 0:
    default_role = Role(role_name="Default Role", color="grey")
    db.session.add(default_role)
    db.session.commit()

from base64 import b64decode
@app.route("/auth/<nextURL>", methods=['GET', 'POST'])
@login_required
def oAUTH(nextURL):
  oform = OAUTHForm()
  bf = b64decode(nextURL).decode("utf-8")
  oauth_settings = {
    'username': bool(request.args.get('user', default = 1, type = int)),
    'profile_picture': bool(request.args.get('prop', default = 0, type = int)),
  }
  odata = {
      'username': current_user.username if oauth_settings['username'] else None,
      'profile_picture':  url_for('static', filename='/imgs/user/'+current_user.profile_pic, _external=True) if oauth_settings['profile_picture'] else None
    }
  return render_template('oauth.html', oauth_settings=oauth_settings, oform=oform, bf=bf, odata=odata)

@app.errorhandler(404)
def page_not_found(e):
  return render_template('404.html'), 404

def Main():
  app.jinja_env.globals.update(settings=app_settings,
                               daysBetween = tools.days_between,
                               currently_online=getOnline,
                               getNewThreads=getNewThreads)
  print('Starting monitor...')
  checker = Thread(target=validate_online, daemon=True)
  checker.start()
  print('Serving app...')
  serve(app, host='0.0.0.0', port=8080, threads=8)

if __name__ == '__main__':
  Main()