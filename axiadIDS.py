from bs4 import BeautifulSoup
import requests

from flask import Flask, render_template, flash, request, redirect, url_for, session
from wtforms import Form, TextField, TextAreaField, validators, StringField, SubmitField
import webbrowser

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from celery import Celery

from PIL import Image
import requests
from io import BytesIO

import hashlib

broker_url = 'amqp://guest@localhost'          # Broker URL for RabbitMQ task queue

app = Flask(__name__)    
celery = Celery(app.name, broker=broker_url)
# celery.config_from_object('celeryconfig')      # Your celery configurations in a celeryconfig.py

# https://console.firebase.google.com/project/test-3bb75/database/firestore/data~2Fusers~2Falovelace

# Use a service account
cred = credentials.Certificate('test-3bb75-firebase-adminsdk-4effm-2cd12b5de1.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# App config.
DEBUG = True
app = Flask(__name__)
app.config.from_object(__name__)
app.config['SECRET_KEY'] = '7d441f27d441f27567d441f2b6176a'

# example url: https://www.imdb.com/title/tt0423409
# Add data
def addData(hex_dig, time, url, src, size):
	doc_ref = db.collection('ha').document(hex_dig)
	doc_ref.set({
		'timeStamp':time,
		'url': url,
		'src':src,
		'size': size
	})

# Read data
def readData(hex_dig, url):
	pics_ref = db.collection('ha')
	docs = pics_ref.stream()
	# print(docs)
	for doc in docs:
		if doc.id == hex_dig:
			d = doc.to_dict()
			if d['url'] == url:
				return d
				# print(u'{} => {}'.format(doc.id, doc.to_dict()))
	return None

class ReusableForm(Form):
	url = TextField('Url:', validators=[validators.required()])

def DownloadLogFile(url = None):
	if url:
		webbrowser.open_new_tab(url)
	else:
		flash('Error: No image sizes to compare :(')

def createHash(url):
	hash_object = hashlib.sha512(url.encode())
	hex_dig = hash_object.hexdigest()
	return hex_dig

def getWidthHeight(data):
	response = requests.get(data)
	img = Image.open(BytesIO(response.content))
	w, h = img.size
	### Another way to get largest photo, but not all photo's have width and height ###
	# print('\n',w,h, res.get('src'),'\n')
	# h = res.get('height')
	# w = res.get('width')
	return w, h

# ### Gets max size photo
@celery.task(bind=True)
def getMaxPhotoFromUrl(self, hex_dig, url, update=False):
	if update == False:
		d = readData(hex_dig, url)
		if d:
			# print("Already have the image!")
			return d
	r  = requests.get(url)
	data = r.text
	soup = BeautifulSoup(data, 'html.parser')
	# soup = BeautifulSoup(urlopen(url))
	h, w, m = 0, 0, 0
	path = None
	for res in soup.findAll('img'):
		w, h = getWidthHeight(res.get('src'))
		if h and w:
			tmpM = int(h) * int(w)
			if tmpM > m:
				m = tmpM
				# print(res.get('src'), w, h)
				path = res.get('src')
	if path:
		addData(hex_dig, 14, url, path, m)
		DownloadLogFile(path)
	else:
		flash("Error: No size of images.")
	return None

@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404</h1><p>The resource could not be found.</p>", 404

@app.route("/update", methods=['GET', 'POST'])
def update():
	form = ReusableForm(request.form)

	# print(form.errors)
	if request.method == 'POST':
		# print("YOOOOOOOOOOO", form.yes, form.no)
		yes_no=list(request.form.to_dict().keys())[0]
		# print('\nYes:', yes_no)
		if yes_no == 'yes':
			session['toUpdate'] = 1
		elif yes_no == 'no':
			session['toUpdate'] = 0
		else:
			db.collection('ha').document(session['hex_dig']).delete()
		return redirect('/')

	return render_template('check.html', form=form)

@app.route("/", methods=['GET', 'POST'])
def hello():
	form = ReusableForm(request.form)
	if 'toUpdate' in session and session['toUpdate'] != None:
		if session['toUpdate'] == 1:
			getMaxPhotoFromUrl(session['hex_dig'], session['url'], update=True)
		else:
			DownloadLogFile(session['src'])
		session['toUpdate'] = None
		# print("SESSION toUpdate:", session['toUpdate'], session['hex_dig'], session['url'], session['src'])
		return render_template('hello.html', form=form)

	print(form.errors)
	if request.method == 'POST':
		url=request.form['url']
		if url != '':
			# print(url)
			hex_dig = createHash(url)
			# print(hex_dig)
			d = getMaxPhotoFromUrl(hex_dig, url)
			if d:
				session['hex_dig'] = hex_dig
				session['url'] = url
				session['src'] = d['src']
				return redirect("/update")
			if form.validate():
				flash('Thanks for using the site!')
			else:
				flash('Error: Enter a URL. ')

	return render_template('hello.html', form=form)

if __name__ == "__main__":
	app.run(debug=DEBUG)

