from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'monitors',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('dates', sa.Text(), nullable=False),
        sa.Column('theatres', sa.Text(), nullable=False),
        sa.Column('interval_min', sa.Integer(), nullable=False),
        sa.Column('baseline', sa.Integer(), nullable=False),
        sa.Column('state', sa.Text(), nullable=False),
        sa.Column('snooze_until', sa.Integer()),
        sa.Column('owner_chat_id', sa.Text()),
        sa.Column('mode', sa.Text(), server_default='FIXED'),
        sa.Column('rolling_days', sa.Integer(), server_default='0'),
        sa.Column('end_date', sa.Text()),
        sa.Column('time_start', sa.Text()),
        sa.Column('time_end', sa.Text()),
        sa.Column('heartbeat_minutes', sa.Integer(), server_default='180'),
        sa.Column('created_at', sa.Integer()),
        sa.Column('updated_at', sa.Integer()),
        sa.Column('last_run_ts', sa.Integer()),
        sa.Column('last_alert_ts', sa.Integer()),
        sa.Column('reload', sa.Integer(), server_default='0'),
    )
    op.create_table(
        'seen',
        sa.Column('monitor_id', sa.String(), nullable=False),
        sa.Column('date', sa.String(), nullable=False),
        sa.Column('theatre', sa.String(), nullable=False),
        sa.Column('time', sa.String(), nullable=False),
        sa.Column('first_seen_ts', sa.Integer()),
        sa.PrimaryKeyConstraint('monitor_id', 'date', 'theatre', 'time')
    )
    op.create_table(
        'theatres_index',
        sa.Column('monitor_id', sa.String(), nullable=False),
        sa.Column('date', sa.String(), nullable=False),
        sa.Column('theatre', sa.String(), nullable=False),
        sa.Column('last_seen_ts', sa.Integer()),
        sa.PrimaryKeyConstraint('monitor_id', 'date', 'theatre')
    )
    op.create_table(
        'runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('monitor_id', sa.String(), nullable=False),
        sa.Column('started_ts', sa.Integer()),
        sa.Column('finished_ts', sa.Integer()),
        sa.Column('status', sa.Text()),
        sa.Column('error', sa.Text()),
    )
    op.create_table(
        'snapshots',
        sa.Column('monitor_id', sa.String(), nullable=False),
        sa.Column('date', sa.String(), nullable=False),
        sa.Column('theatre', sa.String(), nullable=False),
        sa.Column('times_json', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.Integer()),
        sa.PrimaryKeyConstraint('monitor_id', 'date', 'theatre')
    )
    op.create_table(
        'daily',
        sa.Column('chat_id', sa.String(), primary_key=True),
        sa.Column('hhmm', sa.String(), nullable=False),
        sa.Column('enabled', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_sent_ts', sa.Integer()),
    )
    op.create_table(
        'ui_sessions',
        sa.Column('chat_id', sa.String(), nullable=False),
        sa.Column('monitor_id', sa.String(), nullable=False),
        sa.Column('data_json', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('chat_id', 'monitor_id')
    )

def downgrade() -> None:
    op.drop_table('ui_sessions')
    op.drop_table('daily')
    op.drop_table('snapshots')
    op.drop_table('runs')
    op.drop_table('theatres_index')
    op.drop_table('seen')
    op.drop_table('monitors')
