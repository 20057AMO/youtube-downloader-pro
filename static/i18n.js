/* ─────────────────────────────────────────────
   YouTube Downloader Pro - Internationalization
   ───────────────────────────────────────────── */

const translations = {
  ar: {
    // Preloader
    preloaderText: 'جاري التحميل...',

    // Nav
    navDownload: 'التحميل',
    navHistory: 'المكتبة',

    // Hero
    heroBadge: 'تجربة تحميل جديدة كلياً',
    heroTitle1: 'حمّل فيديوهاتك',
    heroTitle2: 'بذكاء وسرعة',
    heroSubtitle: 'حمل فيديوهاتك المفضلة وقوائم التشغيل بأعلى جودة وبضغطة زر واحدة',

    // Input
    inputPlaceholder: 'الصق رابط الفيديو أو الـ Playlist هنا...',
    fetchBtn: 'استعلام',

    // Options
    qualityLabel: 'الجودة',
    qualityBest: 'أفضل جودة ممكنة',
    formatLabel: 'صيغة التحميل',
    formatVideo: 'فيديو (MP4)',
    formatAudio: 'صوت (MP3)',

    // Info Card
    badgePlaylist: 'قائمة تشغيل',
    badgeVideo: 'فيديو مفرد',
    badgeCount: 'مقطع فيديو',
    badgeViews: 'مشاهدة',
    downloadPlaylist: 'تحميل القائمة بالكامل',
    downloadStart: 'بدء التحميل الآن',

    // Progress
    progressPreparing: 'جاري التجهيز...',
    progressFetching: 'جلب البيانات...',
    progressDownloading: 'جاري التحميل...',
    progressCompleted: 'اكتمل التحميل بنجاح',
    progressError: 'حدث خطأ غير متوقع',
    progressPlaylistTitle: 'تحميل قائمة التشغيل...',
    progressSingleTitle: 'جاري التحميل...',
    progressItemOf: 'تحميل {0} من {1}',

    // Actions
    openFolder: 'فتح مجلد التنزيلات',
    downloadAnother: 'تحميل فيديو آخر',

    // History
    historyTitle: 'مكتبة التنزيلات',
    historyRefresh: 'تحديث',
    historyEmpty: 'لا توجد ملفات محملة بعد',
    historyItems: 'عناصر',

    // Toasts
    toastLinkError: 'الرجاء إدخال رابط صحيح',
    toastLinkSuccess: 'تم جلب البيانات بنجاح',
    toastDownloadStart: 'بدأ التحميل بنجاح',
    toastFolderOpen: 'تم فتح المجلد بنجاح',
    toastFolderError: 'لا يمكن فتح المجلد على هذا النظام',
    toastFolderRedirect: 'انتقلنا لصفحة المكتبة لتتمكن من تحميل ملفاتك',
    toastServer_error: 'تعذر الاتصال بالخادم',
    toastTooManyTasks: 'الخادم مشغول: تم الوصول إلى الحد الأقصى للمهام. حاول مرة أخرى بعد قليل.',
    toastRateLimited: 'طلبات كثيرة جداً. انتظر قليلاً ثم حاول مرة أخرى.',
    toastNetworkError: 'تعذر الاتصال بالخادم. تحقق من الشبكة وحاول مرة أخرى.',

    // System notices
    ffmpegMissing: 'تنبيه: ffmpeg غير مثبّت على الخادم. معظم فيديوهات يوتيوب الحديثة تحتاج ffmpeg لدمج الصوت والفيديو، والتحويل إلى MP3 معطّل. ثبّت ffmpeg (python install_ffmpeg.py) لتفعيل كل الميزات.',
    dismiss: 'إغلاق',

    // Errors
    errorInvalidData: 'الرجاء إدخال بيانات صحيحة',
    errorInvalidUrl: 'الرجاء إدخال رابط صحيح',
    errorInvalidYouTube: 'الرجاء إدخال رابط يوتيوب صحيح',
    errorInvalidType: 'نوع التحميل غير صحيح',
    errorTaskNotFound: 'المهمة غير موجودة',

    // Misc
    preparing: 'تجهيز الملفات...',
    downloading: 'جاري التحميل...',
    unknown: 'مجهول',
    extraItems: 'و {0} مقطع إضافي',
    errorCount: 'تنبيهات ({0}):',
    errorDetails: 'تفاصيل الخطأ:',
    downloadFile: 'تحميل الملف',
    clearInput: 'مسح الرابط',
  },

  en: {
    // Preloader
    preloaderText: 'Loading...',

    // Nav
    navDownload: 'Download',
    navHistory: 'Library',

    // Hero
    heroBadge: 'A brand new download experience',
    heroTitle1: 'Download your videos',
    heroTitle2: 'with intelligence and speed',
    heroSubtitle: 'Download your favorite videos and playlists in the highest quality with a single click',

    // Input
    inputPlaceholder: 'Paste video or playlist URL here...',
    fetchBtn: 'Fetch',

    // Options
    qualityLabel: 'Quality',
    qualityBest: 'Best possible quality',
    formatLabel: 'Download Format',
    formatVideo: 'Video (MP4)',
    formatAudio: 'Audio (MP3)',

    // Info Card
    badgePlaylist: 'Playlist',
    badgeVideo: 'Single Video',
    badgeCount: 'videos',
    badgeViews: 'views',
    downloadPlaylist: 'Download Entire Playlist',
    downloadStart: 'Start Download Now',

    // Progress
    progressPreparing: 'Preparing...',
    progressFetching: 'Fetching data...',
    progressDownloading: 'Downloading...',
    progressCompleted: 'Download completed successfully',
    progressError: 'An unexpected error occurred',
    progressPlaylistTitle: 'Downloading playlist...',
    progressSingleTitle: 'Downloading...',
    progressItemOf: 'Downloading {0} of {1}',

    // Actions
    openFolder: 'Open Downloads Folder',
    downloadAnother: 'Download Another Video',

    // History
    historyTitle: 'Downloads Library',
    historyRefresh: 'Refresh',
    historyEmpty: 'No files downloaded yet',
    historyItems: 'items',

    // Toasts
    toastLinkError: 'Please enter a valid URL',
    toastLinkSuccess: 'Data fetched successfully',
    toastDownloadStart: 'Download started successfully',
    toastFolderOpen: 'Folder opened successfully',
    toastFolderError: 'Cannot open folder on this system',
    toastFolderRedirect: 'Redirected to Library so you can download your files',
    toastServer_error: 'Could not connect to server',
    toastTooManyTasks: 'The server is busy: the task limit has been reached. Please try again shortly.',
    toastRateLimited: 'Too many requests. Please wait a moment and try again.',
    toastNetworkError: 'Could not connect to the server. Check your connection and try again.',

    // System notices
    ffmpegMissing: 'Heads up: ffmpeg is not installed on the server. Most modern YouTube videos need ffmpeg to merge audio and video, and MP3 conversion is disabled. Install ffmpeg (python install_ffmpeg.py) to enable all features.',
    dismiss: 'Dismiss',

    // Errors
    errorInvalidData: 'Please enter valid data',
    errorInvalidUrl: 'Please enter a valid URL',
    errorInvalidYouTube: 'Please enter a valid YouTube URL',
    errorInvalidType: 'Invalid download type',
    errorTaskNotFound: 'Task not found',

    // Misc
    preparing: 'Preparing files...',
    downloading: 'Downloading...',
    unknown: 'Unknown',
    extraItems: 'and {0} more items',
    errorCount: 'Warnings ({0}):',
    errorDetails: 'Error Details:',
    downloadFile: 'Download File',
    clearInput: 'Clear URL',
  }
};

let currentLang = localStorage.getItem('yt-dl-lang') || 'ar';

function t(key, ...args) {
  let text = translations[currentLang][key] || translations['ar'][key] || key;
  args.forEach((arg, i) => {
    text = text.replace(`{${i}}`, arg);
  });
  return text;
}

function setLanguage(lang) {
  currentLang = lang;
  localStorage.setItem('yt-dl-lang', lang);

  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
  document.body.dir = lang === 'ar' ? 'rtl' : 'ltr';

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const text = t(key);
    if (el.tagName === 'INPUT') {
      el.placeholder = text;
    } else {
      el.textContent = text;
    }
  });

  document.querySelectorAll('[data-i18n-html]').forEach(el => {
    const key = el.getAttribute('data-i18n-html');
    el.innerHTML = t(key);
  });

  document.querySelectorAll('[data-i18n-aria]').forEach(el => {
    const key = el.getAttribute('data-i18n-aria');
    el.setAttribute('aria-label', t(key));
  });

  const langBtn = document.getElementById('langToggle');
  if (langBtn) {
    langBtn.textContent = lang === 'ar' ? 'EN' : 'AR';
  }

  document.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang } }));
}

function toggleLanguage() {
  const newLang = currentLang === 'ar' ? 'en' : 'ar';
  setLanguage(newLang);
}

function getCurrentLang() {
  return currentLang;
}
