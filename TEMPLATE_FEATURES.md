# 📧 Template & Advanced Features Documentation

## ✅ All Features Implemented!

### 1. **Body Content Options**

#### A. Plain Text Body
- Simple text editor for plain text emails
- Use template tags: `{{name}}`, `{{email}}`, `{{tfn}}`, etc.

#### B. HTML Body with Inline Images
- Upload HTML files
- **Automatic Base64 Conversion**: All images in HTML are automatically converted to base64 inline images
- Prevents broken images in emails
- Supports: GIF, PNG, JPEG, JPG, WEBP

**How it works:**
```html
<!-- Before: -->
<img src="logo.png">

<!-- After automatic conversion: -->
<img src="data:image/png;base64,iVBORw0KGgoAAAANS...">
```

### 2. **Attachments with Base64 Encoding**

#### A. Image Attachments
- Upload multiple images (GIF, PNG, JPEG, JPG, WEBP)
- Automatically converted to base64
- Personalized naming: `emailprefix + random4digits + extension`
- Example: `groupleeman4829.jpg`

#### B. PDF Attachments
- Upload multiple PDFs
- Automatically converted to base64
- Personalized naming: `emailprefix + random4digits.pdf`
- Example: `groupleeman4829.pdf`

### 3. **Attachment Naming Logic**

```
Input email: groupleeman@gmail.com
Generated name: groupleeman4829.pdf
                ^^^^^^^^^^  ^^^^
                email       random
                prefix      number
```

- Extracts email prefix (before @)
- Adds random 4-digit number
- Adds file extension
- Does NOT include @domain.com

### 4. **Multiple HTML Content Rotation**

- Upload multiple HTML files
- System rotates through them automatically
- Each email gets next HTML in rotation
- Perfect for A/B testing

### 5. **Subject Line Rotation**

- Add multiple subject lines
- Two input methods:
  1. Single: Add one at a time
  2. Bulk: Paste multiple (one per line)
- Auto-rotation for each email
- Great for testing different subject lines

### 6. **Sender Name Options**

- **Default Mode**: Use SMTP email as sender name
- **Custom Mode**: Upload multiple sender names
- Rotation through custom names
- Two input methods:
  1. Bulk paste (one per line)
  2. List management

### 7. **Custom Template Tags**

Set once, use everywhere:
- `{{name}}` - Recipient name
- `{{email}}` - Recipient email
- `{{firstname}}` - Email prefix
- `{{tfn}}` - Tax File Number
- `{{date}}` - Date
- `{{time}}` - Time
- `{{custom1}}` - Custom field 1
- `{{custom2}}` - Custom field 2

**Example:**
```
Subject: Hello {{name}}, TFN: {{tfn}}
Body: Your appointment on {{date}} at {{time}}
```

### 8. **Persistent Settings**

✅ **Set Once, Use Forever**
- Configure TFN, Date, Time once
- Upload HTML templates
- Set subject lines
- Set sender names
- Clear only SMTP and recipient data
- Keep all other settings!

**Workflow:**
1. First time: Set ALL parameters
2. Next time: Only clear SMTP + Recipients
3. Upload new SMTP sheet
4. Upload new recipient sheet
5. Click START → Everything else is saved!

### 9. **Supported Combinations**

✅ All these combinations work:

| Body Type | Attachment | Supported |
|-----------|-----------|-----------|
| Plain Text | None | ✅ |
| Plain Text | PDF (base64) | ✅ |
| Plain Text | Image (base64) | ✅ |
| Plain Text | Both | ✅ |
| HTML (inline base64) | None | ✅ |
| HTML (inline base64) | PDF (base64) | ✅ |
| HTML (inline base64) | Image (base64) | ✅ |
| HTML (inline base64) | Both | ✅ |

### 10. **Base64 Encryption Benefits**

✅ **Why Base64?**
- Prevents spam filters
- No broken image links
- Email portability
- Professional appearance
- Works in all email clients

### 11. **Sample Format**

#### SMTP Format:
```
email|password|token|client_id

Example:
lxao5455@outlook.com|jnhg8221|M.C503_BAY...|9e5f94bc-e8a4...
```

#### Recipients Format (CSV):
```
Email,Name
john@example.com,John Doe
jane@example.com,Jane Smith
```

#### Subject Lines (Bulk Paste):
```
Special Offer for {{name}}!
Exclusive Deal - {{date}}
Limited Time: {{tfn}}
```

#### Sender Names (Bulk Paste):
```
John Smith
Marketing Team
Support Department
```

### 12. **Tab Organization**

The Templates tab has 5 sub-tabs:

1. **📝 Body Content** - Text or HTML body
2. **📎 Attachments** - Images and PDFs
3. **✉️ Subject Lines** - Multiple subjects with rotation
4. **👤 Sender Names** - Custom or default names
5. **🏷️ Custom Tags** - TFN, Date, Time, etc.

### 13. **Backend Integration**

All features integrated with backend:
- `template_manager.py` - Core template processing
- Base64 conversion for images
- Base64 conversion for PDFs
- HTML inline image conversion
- Template tag replacement
- Rotation logic
- Personalized naming

## 🎯 Complete Feature Checklist

| Feature | Status |
|---------|--------|
| Plain text body | ✅ |
| HTML body upload | ✅ |
| Inline image base64 | ✅ |
| Image attachments (base64) | ✅ |
| PDF attachments (base64) | ✅ |
| Personalized attachment names | ✅ |
| Multiple HTML rotation | ✅ |
| Subject line rotation | ✅ |
| Sender name rotation | ✅ |
| Custom tags (TFN, Date, Time) | ✅ |
| Persistent settings | ✅ |
| All combinations supported | ✅ |

## 🚀 Ready to Use!

All template features are fully implemented and integrated into the UI!
