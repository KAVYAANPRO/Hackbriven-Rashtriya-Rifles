// Image handling utilities

export const ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
export const MAX_IMAGE_SIZE_MB = 10;
export const MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024;

export function isValidImage(file) {
  return ACCEPTED_IMAGE_TYPES.includes(file.type) && file.size <= MAX_IMAGE_SIZE_BYTES;
}

export function getImageDimensions(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve({ width: img.naturalWidth, height: img.naturalHeight });
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Could not load image'));
    };
    img.src = url;
  });
}

export async function resizeImage(file, maxWidth = 1920, maxHeight = 1080, quality = 0.85) {
  const dims = await getImageDimensions(file);
  const scale = Math.min(1, maxWidth / dims.width, maxHeight / dims.height);
  if (scale === 1) return file;

  const canvas = document.createElement('canvas');
  canvas.width = Math.round(dims.width * scale);
  canvas.height = Math.round(dims.height * scale);
  const ctx = canvas.getContext('2d');

  const img = new Image();
  img.src = URL.createObjectURL(file);
  await new Promise((res) => { img.onload = res; });
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  URL.revokeObjectURL(img.src);

  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(new File([blob], file.name, { type: file.type })), file.type, quality);
  });
}
