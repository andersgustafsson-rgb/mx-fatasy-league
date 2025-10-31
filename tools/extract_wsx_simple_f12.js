// Enkel WSX Image Extractor - Klistra in hela denna koden i F12-konsolen

(async function() {
  console.log('🚀 Startar WSX Image Extractor...');
  
  function slugify(s) {
    return (s || '').toLowerCase().trim().replace(/\./g, '').replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
  }
  
  function downloadBlob(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  }
  
  // Hitta alla rider-kort/sektioner
  const riders = [];
  
  // Metod 1: Leta efter alla img-taggar och deras kontext
  console.log('📸 Söker efter bilder...');
  const allImages = Array.from(document.querySelectorAll('img'));
  console.log(`   Hittade ${allImages.length} bilder totalt`);
  
  allImages.forEach((img, idx) => {
    // Hoppa över små ikoner och placeholders
    if (img.width < 80 || img.height < 80) return;
    if (img.src.includes('placeholder') || img.src.includes('logo') || img.src.includes('icon')) return;
    if (img.src.includes('data:image/svg')) return; // Ignorera SVG placeholders
    
    // Hitta namn och nummer nära bilden
    let parent = img.parentElement;
    let name = null;
    let number = null;
    let attempts = 0;
    
    while (parent && attempts < 8) {
      const text = parent.textContent || '';
      
      // Försök hitta nummer (#17, 17, etc.)
      if (!number) {
        const numMatch = text.match(/\b(\d{1,3})\b/);
        if (numMatch && parseInt(numMatch[1]) < 999) {
          number = parseInt(numMatch[1]);
        }
      }
      
      // Försök hitta namn (efter nummer, före komma)
      if (!name && number) {
        const parts = text.split(number.toString());
        if (parts[1]) {
          const namePart = parts[1].split(',')[0].split('\n')[0].trim();
          if (namePart.length > 2 && namePart.length < 40 && !namePart.match(/^\d+$/)) {
            name = namePart;
          }
        }
      }
      
      // Alternativ: leta efter h2/h3 med namn
      const nameEl = parent.querySelector('h2, h3, h4, [class*="name"], [class*="Name"], [class*="title"]');
      if (nameEl && !name) {
        const nameText = nameEl.textContent.trim().split(',')[0].split('\n')[0].trim();
        if (nameText.length > 2 && nameText.length < 40) {
          name = nameText;
        }
      }
      
      parent = parent.parentElement;
      attempts++;
    }
    
    // Om vi har bild men inte namn, försök extrahera från alt-text eller nearby text
    if (!name) {
      if (img.alt && img.alt.length > 2 && img.alt.length < 40) {
        name = img.alt.split(',')[0].trim();
      }
    }
    
    if (img.src && img.src.length > 10) { // Har en riktig bild-URL
      riders.push({
        name: name || `rider_${idx}`,
        number: number,
        imgUrl: img.src,
        width: img.naturalWidth || img.width,
        height: img.naturalHeight || img.height
      });
      
      console.log(`   ✓ [${idx}] ${number || '?'}# ${name || 'Okänt'} (${img.naturalWidth || img.width}x${img.naturalHeight || img.height})`);
    }
  });
  
  // Deduplicera
  const seen = new Set();
  const unique = riders.filter(r => {
    const key = r.imgUrl;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  
  console.log(`\n✅ Totalt ${unique.length} unika riders med bilder`);
  
  if (unique.length === 0) {
    console.error('❌ Inga riders hittades! Prova att scrolla ner på sidan för att ladda in fler riders.');
    return;
  }
  
  // Visa tabell
  console.table(unique.map(r => ({
    Number: r.number || '?',
    Name: r.name,
    'Image size': `${r.width}x${r.height}`,
    URL: r.imgUrl.substring(0, 50) + '...'
  })));
  
  // Fråga om nedladdning
  const proceed = confirm(
    `Hittade ${unique.length} riders med bilder.\n\n` +
    `Vill du ladda ner alla bilder?\n\n` +
    `Format: {nummer}_{namn}.jpg\n` +
    `Nedladdning sker med 300ms mellanrum mellan bilder.`
  );
  
  if (!proceed) {
    console.log('❌ Avbruten av användare');
    return unique;
  }
  
  console.log(`\n📥 Laddar ner ${unique.length} bilder...`);
  
  // Ladda ner alla bilder
  for (let i = 0; i < unique.length; i++) {
    const rider = unique[i];
    const filename = `${rider.number ? rider.number + '_' : ''}${slugify(rider.name)}.jpg`;
    
    try {
      console.log(`   [${i + 1}/${unique.length}] ${filename}...`);
      
      const response = await fetch(rider.imgUrl, { mode: 'cors', cache: 'no-cache' });
      if (!response.ok) {
        console.warn(`   ⚠️ Kunde inte ladda ${filename}: ${response.status}`);
        continue;
      }
      
      const blob = await response.blob();
      downloadBlob(blob, filename);
      
      // Vänta lite mellan nedladdningar
      await new Promise(resolve => setTimeout(resolve, 300));
    } catch (err) {
      console.error(`   ❌ Fel vid nedladdning av ${filename}:`, err);
    }
  }
  
  console.log(`\n✅ Klart! ${unique.length} bilder har laddats ner.`);
  console.log(`\n📋 Nästa steg:`);
  console.log(`   1. Flytta alla .jpg filer till: static/riders/wsx/`);
  console.log(`   2. Kontrollera att filnamnen ser rätt ut`);
  console.log(`   3. Bilder visas automatiskt i appen!`);
  
  return unique;
})();

