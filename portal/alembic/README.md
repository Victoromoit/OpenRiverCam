Generic single-database configuration.
======================================

In general, we recommend to **always backup the entire database before performing any migration activities**.

To make it easier to perform database migrations within running instances with `docker-compose`, a script `alembic.sh`
is available that can be run outside of docker to perform database migration activities while the `docker-compose`
service are running. You can run this script as if you are running alembic directly, with all command line
arguments of alembic between single quotes.

New tables
----------
To generate tables from scratch with a new deployment, run:
```
alembic upgrade head
```

New migration script
--------------------
To prepare a new database migration script after changes in models, run:
```
alembic revision --autogenerate -m "name of change"
```
where `"name of change"` can be replaced by any meaningful succinct string that describes the change made.
Then revise the upgrade and downgrade functions in the prepared migration script to ensure the migration happens in
the way you want, and no data gets lost.

To upgrade a production database after this change do `alembic upgrade head` again.

Stamp database
--------------
To ensure a non-version controlled database gets version controlled to the most recent change, type:
```
alembic stamp head
```
Replace `head` for the revision the database obeys to in case relevant.


