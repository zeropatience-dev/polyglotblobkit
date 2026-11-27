/** Decimal MB; use the same server-defined limit for both checks. */
export function validateFiles(files, maxUploadMb = 50) {
  if (!Number.isSafeInteger(maxUploadMb) || maxUploadMb < 1 ||
      !Number.isSafeInteger(maxUploadMb * 1_000_000)) {
    throw new RangeError('maxUploadMb must be a positive integer within the safe byte range');
  }
  const maxBytes = maxUploadMb * 1_000_000;
  const accepted = [], rejected = [];
  for (const file of files) {
    if (!file || !Number.isSafeInteger(file.size) || file.size < 0) {
      throw new TypeError('Expected File/Blob objects with a valid byte size');
    }
    if (file.size > maxBytes) rejected.push({file, maxBytes, code: 'UPLOAD_TOO_LARGE'});
    else accepted.push(file);
  }
  return {accepted, rejected, maxBytes};
}
