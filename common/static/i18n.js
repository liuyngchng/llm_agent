/**
 * i18n client-side helper.
 * Requires window.__I18N__ (injected by server template) and window.__LANG__.
 */
window.__ = function(key) {
    if (window.__I18N__ && window.__I18N__[key]) {
        return window.__I18N__[key];
    }
    console.warn('i18n: missing key "' + key + '" for lang ' + (window.__LANG__ || '??'));
    return key;
};

window.__fmt = function(key) {
    var s = window.__(key);
    for (var i = 1; i < arguments.length; i++) {
        s = s.replace('{' + (i - 1) + '}', arguments[i]);
    }
    return s;
};

window.__fmt_named = function(key, params) {
    var s = window.__(key);
    for (var k in params) {
        if (params.hasOwnProperty(k)) {
            s = s.replace('{' + k + '}', params[k]);
        }
    }
    return s;
};
