Change everything in the files to english (with no legacy code or alias) and fix everything you found. Do note that apis_externas changed a bit, but feel free to change again.

also some comments:
- db_models to not be a single file... if we REALLY need it, then should be a folder
- seed.py is gonna be deteled (you can read in this plan file, what i changed)
- apis_externas is wrong language name, probably in the wrong place, its outside any folder etc etc. everything in the repo should use port-adapter.
- repositories also shouldnt be a single file.

- remove the sqlalchemy and database things.
we should use sqlite for local database testing (if needed)
it should be data saved on a local file and an optional command to run locally (when we use uvicorn on port), no files that always autopopulate or anything like that.
when we eventually go to gcp, we will use something better than sqlite. gcp should be a folder, we will use adapter, but any databse should work like local, cloud (gcp, aws etc). we wont implement all, but the port-adapter idea should be there.
