"""initial

Revision ID: c2ddd9b8e13b
Revises: 
Create Date: 2026-03-27 00:37:06.313905

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c2ddd9b8e13b'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('submissions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=False),
    sa.Column('work_email', sa.String(length=255), nullable=False),
    sa.Column('crm', sa.Enum('hubspot', 'salesforce', 'zoho', 'odoo', 'other', 'no_crm', name='crmchoice'), nullable=False),
    sa.Column('crm_other', sa.String(length=255), nullable=True),
    sa.Column('company_url', sa.String(length=512), nullable=False),
    sa.Column('team_size', sa.Enum('lt10', 't10_20', 't20_50', 't50_plus', name='teamsize'), nullable=False),
    sa.Column('monthly_leads', sa.Enum('lt100', 'l100_500', 'l500_2000', 'l2000_plus', name='monthlyleads'), nullable=False),
    sa.Column('lead_handling', sa.Enum('all_on_time', 'probably_miss', 'definitely_lose', name='leadhandling'), nullable=False),
    sa.Column('channels_used', sa.JSON(), nullable=False),
    sa.Column('unified_view', sa.Enum('yes', 'partially', 'no', name='unifiedview'), nullable=False),
    sa.Column('upsell_crosssell', sa.Enum('yes_automated', 'manual_only', 'no', name='upsellcrosssell'), nullable=False),
    sa.Column('churn_detection', sa.Enum('proactive', 'manual', 'we_dont', name='churndetection'), nullable=False),
    sa.Column('biggest_frustrations', sa.JSON(), nullable=False),
    sa.Column('status', sa.Enum('pending', 'enriching', 'scoring', 'generating', 'completed', 'failed', name='submissionstatus'), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_submissions_id'), 'submissions', ['id'], unique=False)
    op.create_index(op.f('ix_submissions_work_email'), 'submissions', ['work_email'], unique=False)
    op.create_table('audits',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('submission_id', sa.Integer(), nullable=False),
    sa.Column('cdp_score', sa.Float(), nullable=True),
    sa.Column('ai_agent_score', sa.Float(), nullable=True),
    sa.Column('recommendation_score', sa.Float(), nullable=True),
    sa.Column('analytics_score', sa.Float(), nullable=True),
    sa.Column('total_score', sa.Float(), nullable=True),
    sa.Column('cdp_score_details', sa.JSON(), nullable=True),
    sa.Column('ai_agent_score_details', sa.JSON(), nullable=True),
    sa.Column('recommendation_score_details', sa.JSON(), nullable=True),
    sa.Column('analytics_score_details', sa.JSON(), nullable=True),
    sa.Column('audit_content', sa.JSON(), nullable=True),
    sa.Column('pdf_path', sa.String(length=1024), nullable=True),
    sa.Column('telegram_sent', sa.Integer(), nullable=False),
    sa.Column('sheet_written', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('pending', 'generating', 'completed', 'failed', name='auditstatus'), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audits_id'), 'audits', ['id'], unique=False)
    op.create_index(op.f('ix_audits_submission_id'), 'audits', ['submission_id'], unique=True)
    op.create_table('enrichments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('submission_id', sa.Integer(), nullable=False),
    sa.Column('detected_tools', sa.JSON(), nullable=True),
    sa.Column('raw_data', sa.JSON(), nullable=True),
    sa.Column('signals_count', sa.Integer(), nullable=False),
    sa.Column('industry', sa.String(length=255), nullable=True),
    sa.Column('language', sa.String(length=10), nullable=True),
    sa.Column('geo', sa.String(length=100), nullable=True),
    sa.Column('company_size_signal', sa.String(length=100), nullable=True),
    sa.Column('social_links', sa.JSON(), nullable=True),
    sa.Column('status', sa.Enum('pending', 'in_progress', 'success', 'limited', 'failed', name='enrichmentstatus'), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_enrichments_id'), 'enrichments', ['id'], unique=False)
    op.create_index(op.f('ix_enrichments_submission_id'), 'enrichments', ['submission_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_enrichments_submission_id'), table_name='enrichments')
    op.drop_index(op.f('ix_enrichments_id'), table_name='enrichments')
    op.drop_table('enrichments')
    op.drop_index(op.f('ix_audits_submission_id'), table_name='audits')
    op.drop_index(op.f('ix_audits_id'), table_name='audits')
    op.drop_table('audits')
    op.drop_index(op.f('ix_submissions_work_email'), table_name='submissions')
    op.drop_index(op.f('ix_submissions_id'), table_name='submissions')
    op.drop_table('submissions')
