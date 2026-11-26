Decide the best strategy, use subagents to review somethings i find suspicious and achieve the goal with a consensus. Then change the code. Dont create tests for now.:

# domain:
- domain/services is empty
- domain/types.py exists and is not inside any folder

# infrastructure: 
- infrastructure/adapter/security exists. isnt it an odd choice?
- dont have any from future import annotations. we changed to python 3.15. apply lazy imports as rules suggest. if 
- also would be great if we didnt need logger = logging.getLogger(__name__) in every file, but if its normal, then keep. if its unnecessary boiler or instantiating many times the same thing, then maybe we change.
- im also not sure wether things like __all__ = ["SpotifyAdapter"]
 in the end of a file are actually good practice. review those files.
- isnt music_service kinda thrown there? is this good architecture?

# application:

- evaluate lazy and type checking


- if we need those from_domain in dtos, that map the same names


- in use cases, some have init, others only execute. evaluate.


# presentation:
- we sure need to update those imports based on our import rules
- dependencies.py as a single file with a lot of things. surely bad practice.
- shemas.py should be in the folder schemas. presentation has folders routers and schemas.

# composition.py:
- theres a lot of imports. is this correct? over 150 lines, is it good practice?
- evaluate  lazy and type checking if adequate
- why are we seeding the database? it should be used the local .db file. also, for some reason there are 2 .db files. we shouldnt have any seeding database or creating it. it should be a local one used. in the future, it will connect to gcp.
