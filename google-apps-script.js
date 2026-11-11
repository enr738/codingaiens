/**
 * ==============================================================================
 * نادي البرمجة والذكاء الاصطناعي (Coding AI Club) - ترحيل ومزامنة ردود نموذج Google
 * Google Apps Script Web App Integration (Two-Way Sync: Read & Write)
 * ==============================================================================
 */

function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.tryLock(10000);
  
  try {
    var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = spreadsheet.getActiveSheet();
    
    // إعداد الهيدر التلقائي المطابق للأسئلة
    if (sheet.getLastRow() === 0) {
      var headers = [
        "معرف الرد (ID)",
        "طابع زمني (Timestamp)",
        "حساب Google",
        "الاسم الكامل",
        "القسم / التخصص الدراسي",
        "السنة الدراسية",
        "يوزر تلغرام",
        "هل لديك خبرة سابقة في البرمجة أو الذكاء الاصطناعي؟",
        "اللغات أو التقنيات التي تعرفها",
        "المجالات التي تثير اهتمامك أكثر",
        "المشاركة في لجان تنظيم الأنشطة",
        "الإمكانيات أو المهارات التي يمكنك تقديمها للنادي",
        "المجالات المرغوب تعلمها ضمن الدورات الحضورية"
      ];
      sheet.appendRow(headers);
      
      var headerRange = sheet.getRange(1, 1, 1, headers.length);
      headerRange.setBackground("#673ab7");
      headerRange.setFontColor("#ffffff");
      headerRange.setFontWeight("bold");
      headerRange.setHorizontalAlignment("center");
    }
    
    var rawData = e.postData.contents;
    var data = JSON.parse(rawData);
    var recId = String(data.id || "GF-" + Date.now());

    // منع التكرار في حال المزامنة لنفس المعرّف
    var lastRow = sheet.getLastRow();
    if (lastRow > 1) {
      var ids = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
      for (var i = 0; i < ids.length; i++) {
        if (String(ids[i][0]) === recId) {
          return ContentService.createTextOutput(JSON.stringify({
            status: "success",
            duplicate: true,
            message: "الرد مسجل مسبقاً"
          })).setMimeType(ContentService.MimeType.JSON);
        }
      }
    }
    
    var row = [
      recId,
      data.timestamp || new Date().toLocaleString("ar-DZ"),
      data.account || "",
      data.fullName || "",
      data.major || "",
      data.academicYear || "",
      data.telegramUser || "",
      data.hasExperience || "",
      data.knownTech || "",
      Array.isArray(data.interestDomains) ? data.interestDomains.join(", ") : (data.interestDomains || ""),
      data.committeeJoin || "",
      data.offeredSkills || "",
      Array.isArray(data.learningTopics) ? data.learningTopics.join(", ") : (data.learningTopics || "")
    ];
    
    sheet.appendRow(row);
    
    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      message: "تم حفظ الرد بنجاح في جدول Google Sheets"
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
    
  } finally {
    lock.releaseLock();
  }
}

function doGet(e) {
  var action = e && e.parameter ? e.parameter.action : "";
  if (action === "list") {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var values = sheet.getDataRange().getValues();
    if (values.length <= 1) {
      return ContentService.createTextOutput(JSON.stringify({ ok: true, responses: [] }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    var responses = [];
    for (var i = values.length - 1; i >= 1; i--) {
      var row = values[i];
      if (!row[3]) continue;
      responses.push({
        id: String(row[0] || "GS-" + i),
        timestamp: String(row[1] || ""),
        account: String(row[2] || ""),
        fullName: String(row[3] || ""),
        major: String(row[4] || ""),
        academicYear: String(row[5] || ""),
        telegramUser: String(row[6] || ""),
        hasExperience: String(row[7] || ""),
        knownTech: String(row[8] || ""),
        interestDomains: String(row[9] || "").split(",").map(function(s){ return s.trim(); }).filter(Boolean),
        committeeJoin: String(row[10] || ""),
        offeredSkills: String(row[11] || ""),
        learningTopics: String(row[12] || "").split(",").map(function(s){ return s.trim(); }).filter(Boolean)
      });
    }
    return ContentService.createTextOutput(JSON.stringify({ ok: true, responses: responses }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  return ContentService.createTextOutput("Google Forms Webhook for Coding AI is Active!")
    .setMimeType(ContentService.MimeType.TEXT);
}
