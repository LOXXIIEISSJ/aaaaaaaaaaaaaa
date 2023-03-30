
### Notice
If you want to fork this project--please create a new db.
1. Open Shell
```
rm instance/main.db
```
2. Go to [Secrets] tab and create
	* `'secret'` env (random text)
	*  `'email'`  env (email username) [The email login data here is used to send account confirmation emails]
	*  `'password'`  env (email password)
	* You can check if the envs are in place by using $env_name (*not recommended--only use if needed*)
3. Run the program (this will create a new db)
4. Register a new account
5. Go into `main.py` and find the code
``` 
with app.app_context(): 
		db.create_all()
```
6. Edit to the following:
```
with app.app_context(): 
    db.create_all()
    User.query.filter_by(
      username='your_username').first().admin = True
    db.session.commit()
```
7. Run the program
8. Delete the added code
9. Done! Your account now has admin. Navigate to `/admin` for the admin panel

##### *Note that the forum is still under development and this method will likely improve later on*