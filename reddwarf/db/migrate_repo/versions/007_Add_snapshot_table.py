from sqlalchemy import *
from migrate import *


meta = MetaData()


snapshots = Table('database_snapshots', meta,
               Column('created_at', DateTime(timezone=False)),
               Column('updated_at', DateTime(timezone=False)),
               Column('deleted_at', DateTime(timezone=False)),
               Column('deleted', Boolean(create_constraint=True, name=None)),
               Column('id', Integer(), primary_key=True),
               Column('uuid', String(length=36), index=True, unique=True),
               Column('instance_uuid', String(length=36)),
               Column('name', String(length=255)),
               Column('state', Integer()),
               Column('user_id', String(length=32), index=True, unique=False),
               Column('project_id', String(length=32)),
               Column('storage_uri', String(length=255)),
               Column('storage_user_id', String(length=32)),
               Column('storage_size', Integer()))


def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine; bind
    # migrate_engine to your metadata
    meta.bind = migrate_engine
    snapshots.create()

def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    meta.bind = migrate_engine
    snapshots.drop()

