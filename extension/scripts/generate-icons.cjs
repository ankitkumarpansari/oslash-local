const { createCanvas } = require('canvas');
const fs = require('fs');
const path = require('path');

const sizes = [16, 32, 48, 128];
const outputDir = path.join(__dirname, '../public/icons');

// Ensure output directory exists
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

function createIcon(size, isOffline = false) {
  const canvas = createCanvas(size, size);
  const ctx = canvas.getContext('2d');
  
  // Create rounded rectangle background
  const radius = Math.floor(size * 0.2);
  
  // Gradient background
  const gradient = ctx.createLinearGradient(0, 0, size, size);
  if (isOffline) {
    gradient.addColorStop(0, '#6b7280');
    gradient.addColorStop(1, '#4b5563');
  } else {
    gradient.addColorStop(0, '#6366f1'); // Indigo
    gradient.addColorStop(1, '#8b5cf6'); // Purple
  }
  
  // Draw rounded rectangle
  ctx.beginPath();
  ctx.moveTo(radius, 0);
  ctx.lineTo(size - radius, 0);
  ctx.quadraticCurveTo(size, 0, size, radius);
  ctx.lineTo(size, size - radius);
  ctx.quadraticCurveTo(size, size, size - radius, size);
  ctx.lineTo(radius, size);
  ctx.quadraticCurveTo(0, size, 0, size - radius);
  ctx.lineTo(0, radius);
  ctx.quadraticCurveTo(0, 0, radius, 0);
  ctx.closePath();
  
  ctx.fillStyle = gradient;
  ctx.fill();
  
  // Draw "o/" text
  ctx.fillStyle = 'white';
  ctx.font = `bold ${Math.floor(size * 0.5)}px Arial`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('o/', size / 2, size / 2 + size * 0.05);
  
  return canvas;
}

// Generate all icon sizes
for (const size of sizes) {
  const canvas = createIcon(size);
  const buffer = canvas.toBuffer('image/png');
  const outputPath = path.join(outputDir, `icon-${size}.png`);
  fs.writeFileSync(outputPath, buffer);
  console.log(`Generated: icon-${size}.png`);
}

// Generate offline icon (32px)
const offlineCanvas = createIcon(32, true);
const offlineBuffer = offlineCanvas.toBuffer('image/png');
fs.writeFileSync(path.join(outputDir, 'icon-offline-32.png'), offlineBuffer);
console.log('Generated: icon-offline-32.png');

console.log('\nAll icons generated successfully!');
