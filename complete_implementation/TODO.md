# TODO - Development Roadmap

## 🔥 IMMEDIATE (Do This First)

### Setup & Testing
- [ ] Register Azure AD application
- [ ] Create `.env` file with CLIENT_ID
- [ ] Test application launch: `python app.py`
- [ ] Add one test account
- [ ] Send test email to yourself
- [ ] Verify email delivery (check inbox/spam)

---

## 📌 Phase 2 - Essential Features

### 1. Attachment Support (HIGH PRIORITY)
**Files to modify:**
- `ui/templates.py` - Add attachment selection UI
- `ui/sender.py` - Pass attachments to worker
- `services/send_worker.py` - Use AttachmentProcessor

**Tasks:**
- [ ] Add "Add Attachments" button to Templates tab
- [ ] File picker for multiple files (PDF, images)
- [ ] Display selected attachments in list
- [ ] Integrate `AttachmentProcessor.process_attachments()`
- [ ] Pass attachment data to worker
- [ ] Test with PDF attachment
- [ ] Test with image attachment
- [ ] Test with multiple attachments

**Estimated Time:** 2-3 hours

---

### 2. Inline Base64 Images (HIGH PRIORITY)
**Files to modify:**
- `ui/templates.py` - Add checkbox for inline images
- `services/send_worker.py` - Call HTMLParser.convert_images_to_base64()

**Tasks:**
- [ ] Add "Convert images to inline" checkbox
- [ ] Get base path from HTML file location
- [ ] Call `HTMLParser.convert_images_to_base64()` before sending
- [ ] Test with HTML containing `<img src="logo.png">`
- [ ] Verify image displays in received email

**Estimated Time:** 1-2 hours

---

### 3. Email Preview (MEDIUM PRIORITY)
**New file:** `ui/preview_dialog.py`

**Tasks:**
- [ ] Create preview dialog with QDialog
- [ ] Add "Preview" button to Sender tab
- [ ] Show sample recipient data form
- [ ] Replace tags with sample data
- [ ] Display HTML in QTextBrowser
- [ ] Show attachments list
- [ ] Show subject with replaced tags
- [ ] Add "Send Test Email" button

**Estimated Time:** 3-4 hours

---

### 4. Advanced Pre-Send Validation (MEDIUM PRIORITY)
**Files to modify:**
- `ui/sender.py` - Add validation before start_campaign()

**Tasks:**
- [ ] Check if HTML is empty
- [ ] Check if subjects are empty
- [ ] Check if recipients exist
- [ ] Check if accounts are active
- [ ] Validate all email addresses (regex)
- [ ] Check for missing tags
- [ ] Estimate send time
- [ ] Show validation dialog with warnings
- [ ] Allow user to proceed or cancel

**Estimated Time:** 2-3 hours

---

### 5. Improved Rate Limit Handling (LOW PRIORITY)
**Files to modify:**
- `services/send_worker.py` - Enhance rate limit logic

**Tasks:**
- [ ] Parse Retry-After header from 429 response
- [ ] Implement exponential backoff
- [ ] Track account cooldown periods
- [ ] Store hourly send count per account
- [ ] Add daily limit enforcement
- [ ] Pause account for X minutes after rate limit
- [ ] Show cooldown status in Accounts tab

**Estimated Time:** 3-4 hours

---

## 📌 Phase 3 - Advanced Features

### 6. Campaign Save/Load
**Tasks:**
- [ ] Add "Save Campaign" button to Sender tab
- [ ] Store campaign config in database
- [ ] Add "Load Campaign" button
- [ ] Campaign selector dropdown
- [ ] Restore all settings from saved campaign
- [ ] Campaign history view

**Estimated Time:** 4-5 hours

---

### 7. Template Management
**Tasks:**
- [ ] Save template to database with name
- [ ] Template library view
- [ ] Edit existing template
- [ ] Delete template
- [ ] Duplicate template
- [ ] Template search/filter

**Estimated Time:** 4-5 hours

---

### 8. Retry Queue Management
**Tasks:**
- [ ] Automatic retry scheduling
- [ ] Retry queue tab/view
- [ ] Manual retry button
- [ ] Exponential backoff
- [ ] Max retry limit
- [ ] Clear retry queue

**Estimated Time:** 3-4 hours

---

### 9. Campaign Summary Report
**Tasks:**
- [ ] End-of-campaign dialog
- [ ] Show detailed statistics
- [ ] Time taken, emails/minute
- [ ] Accounts used
- [ ] Success/failure breakdown
- [ ] Export to PDF (using reportlab)
- [ ] Charts using matplotlib

**Estimated Time:** 5-6 hours

---

## 📌 Phase 4 - Production Ready

### 10. Secure Credential Storage
**Tasks:**
- [ ] Research: keyring library
- [ ] Encrypt tokens before database storage
- [ ] Decrypt tokens when needed
- [ ] Windows Credential Manager integration
- [ ] macOS Keychain integration
- [ ] Linux Secret Service integration
- [ ] Master password option

**Estimated Time:** 6-8 hours

---

### 11. Crash Recovery
**Tasks:**
- [ ] Save campaign state every N emails
- [ ] Store last processed recipient ID
- [ ] Detect abnormal shutdown
- [ ] Show "Resume Campaign?" dialog on startup
- [ ] Restore campaign state
- [ ] Continue from last recipient
- [ ] Clear recovery data after completion

**Estimated Time:** 4-5 hours

---

### 12. Campaign Scheduler
**New file:** `ui/scheduler.py`

**Tasks:**
- [ ] Add Schedule tab
- [ ] DateTime picker widget
- [ ] Scheduled campaigns list
- [ ] Background scheduler (APScheduler)
- [ ] Recurring campaigns (daily, weekly)
- [ ] Time zone support
- [ ] Calendar view
- [ ] Start campaign at scheduled time

**Estimated Time:** 8-10 hours

---

### 13. Analytics Dashboard
**Tasks:**
- [ ] Enhanced Dashboard tab
- [ ] Charts for send history (matplotlib)
- [ ] Account performance comparison
- [ ] Template effectiveness
- [ ] Time-series graphs
- [ ] Export analytics to PDF

**Estimated Time:** 6-8 hours

---

### 14. PyInstaller Packaging
**New file:** `build.spec`

**Tasks:**
- [ ] Create PyInstaller spec file
- [ ] Include all dependencies
- [ ] Include database schema
- [ ] Include sample files
- [ ] Test .exe on clean Windows machine
- [ ] Create installer (NSIS or similar)
- [ ] Code signing (optional)
- [ ] Auto-updater (optional)

**Estimated Time:** 6-8 hours

---

## 🧪 Testing

### Unit Tests
**New folder:** `tests/`

**Tasks:**
- [ ] Test tag replacement
- [ ] Test HTML parsing
- [ ] Test attachment processing
- [ ] Test token refresh logic
- [ ] Test account rotation
- [ ] Test database models

**Estimated Time:** 8-10 hours

---

### Integration Tests
**Tasks:**
- [ ] Test full send workflow
- [ ] Test with mock Graph API
- [ ] Test pause/resume
- [ ] Test cancellation
- [ ] Test error handling

**Estimated Time:** 6-8 hours

---

## 📝 Documentation

### User Documentation
**Tasks:**
- [ ] User manual with screenshots
- [ ] Video tutorial (optional)
- [ ] FAQ document
- [ ] Troubleshooting guide
- [ ] Best practices guide

**Estimated Time:** 4-6 hours

---

### Developer Documentation
**Tasks:**
- [ ] Code comments
- [ ] API documentation
- [ ] Architecture diagram
- [ ] Database schema diagram
- [ ] Contributing guidelines

**Estimated Time:** 4-6 hours

---

## 🔧 Improvements & Optimizations

### Performance
- [ ] Database indexing optimization
- [ ] Batch database operations
- [ ] Connection pooling
- [ ] Caching frequently used data
- [ ] Async file I/O

### UI/UX
- [ ] Dark theme option
- [ ] Custom theme support
- [ ] Keyboard shortcuts
- [ ] Tooltips everywhere
- [ ] Context menus
- [ ] Drag-and-drop file upload
- [ ] Undo/redo support

### Security
- [ ] Input sanitization
- [ ] SQL injection prevention (use parameterized queries)
- [ ] XSS prevention in HTML preview
- [ ] Rate limiting on UI actions
- [ ] Audit logging

---

## 🐛 Known Issues to Fix

### Current Issues
- [ ] None yet - report as found

### Future Considerations
- [ ] Handle very large recipient lists (100k+)
- [ ] Memory optimization for attachments
- [ ] Network timeout handling
- [ ] Concurrent account authentication
- [ ] Database migration system

---

## 📊 Metrics to Track

- [ ] Time to send 100 emails
- [ ] Memory usage during campaign
- [ ] CPU usage during campaign
- [ ] Database size growth
- [ ] UI responsiveness

---

## 🎯 Success Criteria

### Phase 1 ✅
- [x] Application launches without errors
- [x] Can add accounts
- [x] Can import recipients
- [x] Can send emails
- [x] UI doesn't freeze during sending
- [x] Logs are recorded

### Phase 2 (Essential)
- [ ] Attachments work
- [ ] Inline images work
- [ ] Preview shows correct data
- [ ] Validation catches errors
- [ ] Rate limiting is intelligent

### Phase 3 (Advanced)
- [ ] Can save/load campaigns
- [ ] Template library is useful
- [ ] Retry queue works
- [ ] Reports are generated

### Phase 4 (Production)
- [ ] Credentials are secure
- [ ] Crash recovery works
- [ ] Scheduler is reliable
- [ ] .exe runs standalone

---

## 📅 Timeline Estimates

- **Phase 2**: 1-2 weeks (part-time)
- **Phase 3**: 2-3 weeks (part-time)
- **Phase 4**: 3-4 weeks (part-time)
- **Testing**: 1 week
- **Documentation**: 1 week

**Total**: ~2-3 months part-time development

---

## 🎉 When to Ship

Ship when:
1. ✅ Phase 1 is complete (DONE!)
2. ✅ Phase 2 is 80% complete
3. ✅ No critical bugs
4. ✅ Basic documentation exists
5. ✅ Tested with real accounts

**Don't wait for perfection. Ship, iterate, improve!**

---

## 💡 Future Ideas

- [ ] Multi-language support (i18n)
- [ ] Cloud sync (save campaigns to cloud)
- [ ] Team collaboration features
- [ ] A/B testing for subject lines
- [ ] Email template marketplace
- [ ] Webhook integrations
- [ ] REST API for automation
- [ ] Mobile companion app
- [ ] Browser extension

---

**Start with Phase 2, Task 1 (Attachments)!** 🚀
