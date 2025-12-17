@accounts_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """Upload session files"""
    if request.method == "POST":
        files = request.files.getlist("session_files")
        
        if not files or files[0].filename == "":
            flash("No files selected", "error")
            return redirect(url_for("accounts.upload"))
        
        uploaded = 0
        skipped = 0
        errors = []
        
        for file in files:
            if file and file.filename.endswith(".session"):
                try:
                    filename = secure_filename(file.filename)
                    phone = filename.replace(".session", "")
                    
                    # Check if account already exists
                    existing = Account.query.filter_by(phone=phone).first()
                    if existing:
                        skipped += 1
                        continue
                    
                    # Save file
                    filepath = os.path.join("uploads/sessions", filename)
                    os.makedirs("uploads/sessions", exist_ok=True)
                    file.save(filepath)
                    
                    # Create account
                    account = Account(
                        phone=phone,
                        session_file_path=filepath,
                        status="pending",
                        health_score=100
                    )
                    db.session.add(account)
                    db.session.flush()
                    
                    # Create device profile
                    device = generate_device_profile()
                    device_profile = DeviceProfile(
                        account_id=account.id,
                        device_model=device["device_model"],
                        system_version=device["system_version"],
                        app_version=device["app_version"],
                        lang_code=device["lang_code"],
                        system_lang_code=device["system_lang_code"]
                    )
                    db.session.add(device_profile)
                    
                    uploaded += 1
                    
                except Exception as e:
                    errors.append(f"{file.filename}: {str(e)}")
        
        db.session.commit()
        
        # Show notifications
        if uploaded > 0:
            flash(f"Successfully uploaded {uploaded} session file(s)", "success")
        if skipped > 0:
            flash(f"Skipped {skipped} duplicate account(s)", "warning")
        for error in errors:
            flash(error, "error")
        
        return redirect(url_for("accounts.list_accounts"))
    
    proxies = Proxy.query.filter_by(status="active").all()
    return render_template("accounts/upload.html", proxies=proxies)
