// Öppna alla WSX-förarbilder i nya flikar så du kan spara dem
// Klistra in hela denna koden i F12-konsolen

(function() {
  console.log('🚀 Startar WSX Image Opener...');
  
  function slugify(s) {
    if (!s) return 'unknown';
    return s.toLowerCase()
      .trim()
      .replace(/\./g, '')
      .replace(/\s+/g, '_')
      .replace(/[^a-z0-9_]/g, '')
      .replace(/_+/g, '_')
      .replace(/^_|_$/g, '');
  }
  
  const riders = [];
  const allImages = Array.from(document.querySelectorAll('img'));
  
  console.log(`📸 Hittade ${allImages.length} bilder totalt`);
  
  // Hitta alla stora bilder (förmodligen rider-foton)
  allImages.forEach((img, idx) => {
    const width = img.naturalWidth || img.width || 0;
    const height = img.naturalHeight || img.height || 0;
    
    // Hoppa över små ikoner
    if (width < 80 || height < 80) return;
    if (img.src.includes('placeholder') || img.src.includes('logo') || img.src.includes('icon')) return;
    if (img.src.includes('data:image/svg')) return;
    if (!img.src || img.src.length < 20) return;
    
    // Hitta namn och nummer
    let parent = img.closest('article, section, div[class*="card"], div[class*="rider"]') || img.parentElement;
    let name = null;
    let number = null;
    let attempts = 0;
    
    while (parent && attempts < 10) {
      const text = parent.textContent || '';
      
      // Hitta nummer
      if (!number) {
        const numMatch = text.match(/\b([1-9]\d{0,2})\b/);
        if (numMatch) {
          const val = parseInt(numMatch[1]);
          if (1 <= val && val <= 999) {
            number = val;
          }
        }
      }
      
      // Hitta namn
      if (!name && number && text.includes(number.toString())) {
        const parts = text.split(number.toString());
        if (parts.length > 1) {
          const candidate = parts[1].split(',')[0].split('\n')[0].trim();
          if (candidate.length >= 2 && candidate.length <= 40 && 
              candidate.match(/^[a-zA-Z\s]+$/) && 
              candidate.toUpperCase() !== 'RIDERS') {
            name = candidate;
            break;
          }
        }
      }
      
      // Leta efter h2/h3/h4
      if (!name) {
        const nameEl = parent.querySelector('h1, h2, h3, h4, h5, [class*="name"], [class*="Name"]');
        if (nameEl) {
          let nameText = nameEl.textContent.trim().split(',')[0].split('\n')[0].trim();
          if (nameText.length >= 2 && nameText.length <= 40 && 
              !nameText.match(/^(CHAMPIONSHIP|RIDERS|ROUND|GP|ON SALE|RESULTS)/i) &&
              nameText.match(/[a-zA-Z]/)) {
            name = nameText;
            break;
          }
        }
      }
      
      parent = parent.parentElement;
      attempts++;
    }
    
    // Rensa namn
    if (name) {
      name = name.replace(/^(CHAMPIONSHIP|RIDERS|ROUND|GP|ON SALE|RESULTS)\s+/i, '');
      name = name.replace(/\s+(CHAMPIONSHIP|RIDERS|ROUND|GP|ON SALE|RESULTS)$/i, '');
      name = name.trim();
    }
    
    // Spara om vi har bild + namn eller nummer
    if ((name || number) && img.src && !img.src.startsWith('data:')) {
      riders.push({
        name: name || `rider_${idx}`,
        number: number,
        imgUrl: img.src
      });
    }
  });
  
  // Deduplicera
  const seen = new Set();
  const unique = riders.filter(r => {
    if (seen.has(r.imgUrl)) return false;
    seen.add(r.imgUrl);
    return true;
  });
  
  console.log(`\n✅ Hittade ${unique.length} unika riders med bilder`);
  
  if (unique.length === 0) {
    console.error('❌ Inga riders hittades! Prova att scrolla ner på sidan först.');
    return;
  }
  
  // Visa vad som hittades
  console.table(unique.map((r, i) => ({
    '#': i + 1,
    Number: r.number || '?',
    Name: r.name,
    Filename: `${r.number ? r.number + '_' : ''}${slugify(r.name)}.jpg`
  })));
  
  // Fråga användaren
  const proceed = confirm(
    `Hittade ${unique.length} riders med bilder.\n\n` +
    `Detta kommer öppna ${unique.length} nya flikar med bilderna.\n\n` +
    `Varje bild kan sedan sparas genom att högerklicka → "Spara bild som..."\n\n` +
    `Filnamnformat: {nummer}_{namn}.jpg\n\n` +
    `Fortätt?`
  );
  
  if (!proceed) {
    console.log('❌ Avbruten');
    return;
  }
  
  // Öppna alla bilder i nya flikar (med fördröjning för att inte överbelasta webbläsaren)
  console.log(`\n🪟 Öppnar ${unique.length} bilder i nya flikar...`);
  console.log('💡 Tips: Gå igenom varje flik och spara bilden med rätt filnamn till static/riders/wsx/');
  
  let opened = 0;
  unique.forEach((rider, idx) => {
    setTimeout(() => {
      const filename = `${rider.number ? rider.number + '_' : ''}${slugify(rider.name)}.jpg`;
      console.log(`   [${idx + 1}/${unique.length}] Öppnar: ${filename}`);
      
      // Öppna bilden i ny flik
      window.open(rider.imgUrl, '_blank');
      
      opened++;
      
      if (opened === unique.length) {
        console.log(`\n✅ Klart! ${opened} flikar öppnade.`);
        console.log(`\n📋 Nästa steg:`);
        console.log(`   1. Gå igenom varje öppnad flik`);
        console.log(`   2. Högerklicka på bilden → "Spara bild som..."`);
        console.log(`   3. Navigera till: C:\\projects\\MittFantasySpel\\static\\riders\\wsx\\`);
        console.log(`   4. Döp filen till det format som visas i konsolen (t.ex. 94_ken_roczen.jpg)`);
        console.log(`   5. Spara!`);
      }
    }, idx * 500); // 500ms mellan varje öppning
  });
  
  return unique;
})();

