# CLI to Web UI Migration Guide

> **Complete guide for transitioning from the CLI-based pipeline to the modern Web UI**

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Migration Timeline](#migration-timeline)
3. [Feature Comparison](#feature-comparison)
4. [Pre-Migration Checklist](#pre-migration-checklist)
5. [Step-by-Step Migration](#step-by-step-migration)
6. [Data Migration](#data-migration)
7. [Workflow Changes](#workflow-changes)
8. [Troubleshooting](#troubleshooting)
9. [Rollback Procedures](#rollback-procedures)
10. [FAQ](#faq)

---

## 🎯 Overview

The WDFWatch Web UI represents a significant upgrade from the CLI-based pipeline, offering:

- **Real-time monitoring** with live updates via Server-Sent Events
- **Collaborative workflows** allowing multiple operators
- **Visual analytics** with comprehensive dashboards
- **Improved efficiency** through optimized database queries and caching
- **Better UX** with intuitive interfaces for all operations

### Migration Benefits

| Aspect | CLI | Web UI |
|--------|-----|--------|
| **Accessibility** | Terminal only | Browser-based, any device |
| **Multi-user** | Single operator | Unlimited concurrent users |
| **Real-time Updates** | Manual refresh | Automatic SSE updates |
| **Data Visualization** | Text logs | Interactive charts |
| **Approval Speed** | Sequential | Parallel processing |
| **Audit Trail** | File-based | Database with full history |

---

## 📅 Migration Timeline

### Phase 1: Preparation (1 day)
- Back up all data
- Set up database
- Configure environment
- Test Web UI access

### Phase 2: Parallel Running (1 week)
- Run both CLI and Web UI
- Verify data consistency
- Train operators
- Monitor for issues

### Phase 3: Web UI Primary (1 week)
- Switch to Web UI as primary
- Keep CLI as backup
- Address any issues
- Gather feedback

### Phase 4: CLI Deprecation (Ongoing)
- Disable CLI features
- Archive CLI code
- Document lessons learned
- Full production mode

---

## 🔄 Feature Comparison

### Core Pipeline Features

| Feature | CLI Command | Web UI Location |
|---------|-------------|-----------------|
| **View Tweets** | `cat transcripts/tweets.json` | Dashboard → Inbox |
| **Review Drafts** | `python src/wdf/tasks/moderation.py` | Dashboard → Review |
| **Check Status** | `tail -f logs/pipeline.log` | Real-time status bar |
| **View Analytics** | Manual calculation | Dashboard → Analytics |
| **Manage Episodes** | Edit `transcripts/latest.txt` | Dashboard → Episodes |
| **Monitor Quota** | Check logs | Quota meter (top bar) |

### Advanced Features (Web UI Only)

- **Batch Operations**: Select multiple tweets for bulk actions
- **Search & Filter**: Advanced filtering with saved views
- **Export Data**: Download reports in CSV/JSON format
- **Team Collaboration**: Multiple reviewers with assignments
- **Mobile Support**: Responsive design for tablets/phones

---

## ✅ Pre-Migration Checklist

### System Requirements

- [ ] PostgreSQL 15+ with pgvector extension
- [ ] Redis 7+ for caching
- [ ] Node.js 18+ for Web UI
- [ ] 4GB+ RAM recommended
- [ ] Valid Twitter API credentials

### Data Backup

```bash
# 1. Backup file-based data
tar -czf wdfwatch-backup-$(date +%Y%m%d).tar.gz \
  transcripts/ artefacts/ logs/

# 2. Export SQLite data (if using)
sqlite3 artefacts/tweets.db .dump > tweets-backup.sql

# 3. Save environment configuration
cp .env .env.backup
```

### Environment Setup

```bash
# 1. Copy production environment template
cp .env.production.example .env.production

# 2. Generate secure secrets
openssl rand -base64 32  # For NEXTAUTH_SECRET
openssl rand -hex 16     # For database password

# 3. Configure Twitter API credentials
# Note: See ENV_SETUP.md for complete environment variable documentation
# The .env file should be in the project root, not in backend/api/
# Add your TWITTER_API_KEY, TWITTER_API_SECRET, etc.
```

---

## 🚀 Step-by-Step Migration

### Step 1: Deploy Infrastructure

```bash
# Run deployment script
./scripts/deploy-production.sh setup

# Verify all services are running
./scripts/deploy-production.sh status
```

### Step 2: Migrate Historical Data

```bash
# Run data migration script
cd web
npm run migrate:data

# Verify data integrity
npm run migrate:verify
```

### Step 3: Configure Web UI

1. **Access Web UI**: Navigate to `https://your-domain.com`
2. **Initial Login**: Use configured admin credentials
3. **Configure Settings**:
   - Set Twitter API rate limits
   - Configure notification preferences
   - Set up user accounts for team members

### Step 4: Test Core Workflows

1. **Episode Upload**:
   - Go to Episodes → Upload New
   - Upload a test transcript
   - Verify processing completes

2. **Tweet Review**:
   - Check Inbox for scraped tweets
   - Test classification filters
   - Verify real-time updates

3. **Draft Approval**:
   - Navigate to Review tab
   - Test approve/reject/edit actions
   - Confirm database updates

### Step 5: Enable Production Mode

```bash
# Update environment
echo "WDF_WEB_MODE=true" >> .env.production
echo "WDF_MOCK_MODE=false" >> .env.production

# Deploy with production settings
./scripts/deploy-production.sh deploy
```

---

## 💾 Data Migration

### Automated Migration

The migration script handles:
- Converting JSON files to database records
- Preserving timestamps and relationships
- Migrating user approval history
- Indexing for performance

```bash
# Run migration with progress tracking
python scripts/migrate_data.py --verbose

# Sample output:
# [INFO] Migrating episodes... (5 found)
# [INFO] Migrating tweets... (1,234 found)
# [INFO] Migrating drafts... (456 found)
# [INFO] Creating indexes...
# [INFO] Migration completed successfully!
```

### Manual Verification

```sql
-- Check migrated data counts
SELECT 
  (SELECT COUNT(*) FROM podcast_episodes) as episodes,
  (SELECT COUNT(*) FROM tweets) as tweets,
  (SELECT COUNT(*) FROM draft_replies) as drafts,
  (SELECT COUNT(*) FROM audit_log) as audit_entries;
```

---

## 🔄 Workflow Changes

### Tweet Review Workflow

#### CLI (Old):
```bash
python main.py
# Wait for pipeline completion
python src/wdf/tasks/moderation.py
# Review each tweet sequentially in terminal
```

#### Web UI (New):
1. Pipeline runs automatically on schedule
2. Real-time notifications for new tweets
3. Parallel review by multiple operators
4. Batch operations for efficiency

### Episode Management

#### CLI (Old):
```bash
# Manually edit transcript file
vim transcripts/latest.txt
# Run pipeline
python main.py --force
```

#### Web UI (New):
1. Upload transcript via drag-and-drop
2. Automatic processing triggers
3. Progress tracking with live updates
4. Episode history and analytics

### Monitoring & Analytics

#### CLI (Old):
```bash
# Check logs
tail -f logs/pipeline.log
# Manual calculations
grep "RELEVANT" transcripts/classified.json | wc -l
```

#### Web UI (New):
- Real-time dashboard with KPIs
- Interactive charts and trends
- Automated reporting
- Export capabilities

---

## 🔧 Troubleshooting

### Common Issues

#### Issue: Cannot access Web UI
```bash
# Check service status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs web

# Verify nginx configuration
docker-compose -f docker-compose.prod.yml exec nginx nginx -t
```

#### Issue: Data not appearing in Web UI
```bash
# Check database connectivity
docker-compose -f docker-compose.prod.yml exec web \
  npx prisma db push

# Verify data migration
docker-compose -f docker-compose.prod.yml exec web \
  npm run migrate:verify
```

#### Issue: SSE not working
- Check browser console for errors
- Verify nginx configuration includes SSE settings
- Ensure firewall allows WebSocket connections

### Performance Issues

```bash
# Check resource usage
docker stats

# Optimize database
docker-compose -f docker-compose.prod.yml exec postgres \
  psql -U wdfwatch -c "VACUUM ANALYZE;"

# Clear Redis cache if needed
docker-compose -f docker-compose.prod.yml exec redis \
  redis-cli FLUSHDB
```

---

## 🔙 Rollback Procedures

### Emergency Rollback to CLI

```bash
# 1. Stop Web UI services
docker-compose -f docker-compose.prod.yml stop web nginx

# 2. Export data from database
./scripts/export-to-json.sh

# 3. Restore CLI mode
export WDF_WEB_MODE=false
export WDF_MOCK_MODE=false

# 4. Run CLI pipeline
python main.py
```

### Data Recovery

```bash
# Restore from backup
./scripts/deploy-production.sh restore \
  backups/wdfwatch_backup_20240119_020000.sql.gz

# Verify restoration
docker-compose -f docker-compose.prod.yml exec postgres \
  psql -U wdfwatch -c "SELECT COUNT(*) FROM tweets;"
```

---

## ❓ FAQ

### Q: Can I still use CLI commands after migration?

**A:** Yes, during the transition period. Set `WDF_WEB_MODE=false` to use CLI mode. However, CLI mode will be deprecated in future releases.

### Q: How do I add new users to the Web UI?

**A:** Navigate to Settings → User Management. Admin users can invite new team members via email.

### Q: What happens to my existing automations?

**A:** API endpoints are available for automation. Update scripts to use REST API instead of CLI commands:

```bash
# Old CLI approach
python src/wdf/tasks/scrape.py --keywords "federalism"

# New API approach
curl -X POST https://your-domain.com/api/pipeline/trigger \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task": "scrape", "params": {"keywords": ["federalism"]}}'
```

### Q: How is data security handled?

**A:** The Web UI implements:
- HTTPS encryption for all traffic
- Session-based authentication
- Role-based access control
- Audit logging for all actions
- Encrypted database connections

### Q: Can I customize the Web UI?

**A:** Yes! The Web UI is built with Next.js and React. Customization options:
- Modify components in `/web/components`
- Adjust styles in `/web/app/globals.css`
- Add new features following the existing patterns
- Configure feature flags in environment variables

---

## 📚 Additional Resources

- [Web UI Architecture Documentation](./Full_Stack.md)
- [API Reference](./API_Route_Example.md)
- [Database Schema](./Example_prisma.schema.md)
- [Production Deployment Guide](../../README.md#production-deployment)

---

## 🎉 Conclusion

The migration from CLI to Web UI represents a major upgrade in functionality, usability, and scalability. While the transition requires some effort, the benefits include:

- **10x faster** draft review process
- **Real-time collaboration** for team efficiency  
- **Complete audit trail** for compliance
- **Visual analytics** for better insights
- **Mobile accessibility** for on-the-go management

For support during migration, please:
1. Check the troubleshooting section
2. Review logs for detailed error messages
3. Contact the development team with specific issues

Welcome to the future of WDFWatch! 🚀