<?php
/* Explicit, opt-in collector v3. Never installed or requested by default scan. */
header('Content-Type: application/json');
header('Cache-Control: no-store');
$nonce = $_SERVER['HTTP_X_WEBPATCH_CHALLENGE'] ?? '';
$callback = $_SERVER['HTTP_X_WEBPATCH_CALLBACK'] ?? '';
$scope = $_SERVER['HTTP_X_WEBPATCH_SCOPE'] ?? '';
if (($_SERVER['REMOTE_ADDR'] ?? '') !== '127.0.0.1' || ($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET'
    || !preg_match('/^[a-f0-9]{64}$/D', $nonce) || !preg_match('/^webpatch-[a-f0-9]{48}$/D', $callback)
    || !preg_match('/^[a-f0-9]{64}$/D', $scope) || !function_exists('socket_create')) {
    http_response_code(403); echo '{}'; exit;
}
$settings = ini_get_all(null, false);
ksort($settings);
$baselineSettings = $settings;
unset($baselineSettings['memory_hard_limit_percent'], $baselineSettings['max_multipart_body_parts']);
$reviewedDirective = ['state' => 'ABSENT'];
if (array_key_exists('memory_hard_limit_percent', $settings)) {
    $value = $settings['memory_hard_limit_percent'];
    if ($value === null || $value === '' || $value === '-1') {
        $reviewedDirective = ['state' => 'VENDOR_DEFAULT'];
    } elseif (is_string($value) && preg_match('/^[0-9]{3,10}$/D', $value) && (int)$value >= 100) {
        $reviewedDirective = ['state' => 'EXPLICIT_VALUE', 'value' => $value];
    } else {
        $reviewedDirective = ['state' => 'UNKNOWN'];
    }
}
$multipartDirective = ['state' => 'ABSENT'];
if (array_key_exists('max_multipart_body_parts', $settings)) {
    $value = $settings['max_multipart_body_parts'];
    if ($value === '-1') {
        $multipartDirective = ['state' => 'VENDOR_DEFAULT'];
    } elseif (is_string($value) && preg_match('/^[0-9]{1,10}$/D', $value)) {
        $multipartDirective = ['state' => 'EXPLICIT_VALUE', 'value' => $value];
    } else {
        $multipartDirective = ['state' => 'UNKNOWN'];
    }
}
$extensions = get_loaded_extensions();
sort($extensions);
$scanned = php_ini_scanned_files();
$iniFiles = $scanned ? array_values(array_filter(array_map('trim', explode(',', $scanned)))) : [];
sort($iniFiles);
$payload = json_encode([
    'protocol' => 3, 'challenge' => $nonce, 'scope' => $scope, 'pid' => getmypid(),
    'sapi' => PHP_SAPI, 'script' => __FILE__, 'source_sha256' => hash_file('sha256', __FILE__),
    'ini_file' => php_ini_loaded_file(), 'ini_scanned' => $iniFiles,
    'effective_ini_sha256' => hash('sha256', json_encode($settings)),
    'effective_ini_baseline_sha256' => hash('sha256', json_encode($baselineSettings)),
    'reviewed_directives' => ['memory_hard_limit_percent' => $reviewedDirective, 'max_multipart_body_parts' => $multipartDirective],
    'extensions_sha256' => hash('sha256', json_encode($extensions)),
    'cached_script' => function_exists('opcache_is_script_cached') && opcache_is_script_cached(__FILE__),
    'request_path' => parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH),
], JSON_UNESCAPED_SLASHES);
$socket = socket_create(AF_UNIX, SOCK_DGRAM, 0);
if ($socket === false || $payload === false || strlen($payload) > 65536
    || !@socket_connect($socket, "\0" . $callback)
    || @socket_send($socket, $payload, strlen($payload), 0) !== strlen($payload)) {
    http_response_code(503); echo '{}'; exit;
}
socket_close($socket);
echo json_encode(['challenge' => $nonce, 'payload_sha256' => hash('sha256', $payload)]);
