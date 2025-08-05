# Run n8n RSS parallel validation

**Status**: Not Started
**Priority**: Medium
**Category**: Testing/Migration
**Effort**: 2 weeks

## Description
Run both Python RSS agent and n8n workflow in parallel for 2 weeks to validate quality, performance, and reliability before cutover.

## Tasks
- [ ] Enable both systems to run simultaneously
- [ ] Create comparison dashboard
- [ ] Daily quality checks:
  - [ ] Article counts match
  - [ ] Scoring consistency
  - [ ] Task extraction accuracy
  - [ ] Obsidian note quality
- [ ] Performance monitoring:
  - [ ] Processing time comparison
  - [ ] Resource usage
  - [ ] Error rates
- [ ] Collect user feedback on digests
- [ ] Document any discrepancies
- [ ] Create cutover checklist
- [ ] Plan rollback procedure

## Metrics to Track
- Articles processed per run
- Notes created per run
- Tasks extracted accuracy
- Processing time
- Error frequency
- User satisfaction

## Dependencies
- Task 57: Digest workflow implemented
- Both systems fully functional

## Success Criteria
- 14 days of parallel running
- <5% discrepancy in results
- n8n performance equal or better
- No critical errors in n8n
- User approves digest quality