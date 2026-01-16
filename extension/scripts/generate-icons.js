const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

const sizes = [16, 32, 48, 128];
const outputDir = path.join(__dirname, '../public/icons');

// Ensure output directory exists
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

// Create a simple "O/" icon SVG
const createSvg = (size) => {
  const fontSize = Math.floor(size * 0.5);
  const padding = Math.floor(size * 0.1);
  
  return `
    <svg width="${size}" height="${size}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:#6366f1"/>
          <stop offset="100%" style="stop-color:#8b5cf6"/>
        </linearGradient>
      </defs>
      <rect width="${size}" height="${size}" rx="${Math.floor(size * 0.2)}" fill="url(#bg)"/>
      <text 
        x="${size/2}" 
        y="${size/2 + fontSize * 0.35}" 
        font-family="Arial, sans-serif" 
        font-size="${fontSize}px" 
        font-weight="bold" 
        fill="white" 
        text-anchor="middle"
      >o/</text>
    </svg>
  `;
};

async function generateIcons() {
  for (const size of sizes) {
    const svg = createSvg(size);
    const outputPath = path.join(outputDir, `icon-${size}.png`);
    
    await sharp(Buffer.from(svg))
      .png()
      .toFile(outputPath);
    
    console.log(`Generated: icon-${size}.png`);
  }
  
  // Also create an offline version (grayscale)
  const offlineSvg = `
    <svg width="32" height="32" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#6b7280"/>
      <text 
        x="16" 
        y="22" 
        font-family="Arial, sans-serif" 
        font-size="16px" 
        font-weight="bold" 
        fill="white" 
        text-anchor="middle"
      >o/</text>
    </svg>
  `;
  
  await sharp(Buffer.from(offlineSvg))
    .png()
    .toFile(path.join(outputDir, 'icon-offline-32.png'));
  
  console.log('Generated: icon-offline-32.png');
  console.log('All icons generated successfully!');
}

generateIcons().catch(console.error);

