// WSX Image Extractor - Fixad version med bättre filnamnshantering
// Klistra in hela denna koden i F12-konsolen

(async function() {
  console.log('🚀 Startar WSX Image Extractor (fixad version)...');
  
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
  
  function downloadBlob(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 100);
  }
  
  // Samla alla riders med bilder
  const riders = [];
  const allImages = Array.from(document.querySelectorAll('img'));
  
  console.log(`📸 Hittade ${allImages.length} bilder totalt på sidan`);
  
  // Första passet: Hitta alla stora bilder (förmodligen rider-foton)
  allImages.forEach((img, idx) => {
    // Hoppa över små ikoner
    const width = img.naturalWidth || img.width || 0;
    const height = img.naturalHeight || img.height || 0;
    
    if (width < 80 || height < 80) return;
    if (img.src.includes('placeholder') || img.src.includes('logo') || img.src.includes('icon')) return;
    if (img.src.includes('data:image/svg')) return;
    if (!img.src || img.src.length < 20) return;
    
    // Hitta namn och nummer i närheten
    let parent = img.closest('article, section, div[class*="card"], div[class*="rider"]') || img.parentElement;
    let name = null;
    let number = null;
    let attempts = 0;
    
    // Strategi 1: Gå uppåt i DOM-trädet
    while (parent && attempts < 10) {
      const text = parent.textContent || '';
      
      // Hitta nummer (första 1-3 siffror som inte är år)
      if (!number) {
        const nums = text.match(/\b(\d{1,3})\b/g);
        if (nums) {
          for (const n of nums) {
            const val = parseInt(n);
            if (val >= 1 && val <= 999) {
              // Undvik årtal (2024, 2025, etc.)
              if (val < 1900 && val > 0) {
                number = val;
                break;
              }
            }
          }
        }
      }
      
      // Hitta namn: leta efter text efter nummer
      if (!name && number && text.includes(number.toString())) {
        const parts = text.split(number.toString());
        if (parts.length > 1) {
          for (let i = 1; i < parts.length; i++) {
            const candidate = parts[i].split(',')[0].split('\n')[0].trim();
            // Kolla om det ser ut som ett namn (2-30 tecken, inga specialtecken förutom mellanslag)
            if (candidate.length >= 2 && candidate.length <= 30 && 
                candidate.match(/^[a-zA-Z\s]+$/) && candidate !== 'RIDERS') {
              name = candidate;
              break;
            }
          }
        }
      }
      
      // Alternativ: leta efter h1-h4 eller element med "name" i class
      if (!name) {
        const nameEl = parent.querySelector('h1, h2, h3, h4, h5, [class*="name"], [class*="Name"], [class*="title"], [class*="Title"]');
        if (nameEl) {
          let nameText = nameEl.textContent.trim();
          // Ta bort extra info (land, team, etc.)
          nameText = nameText.split(',')[0].split('\n')[0].trim();
          // Filtrera bort "CHAMPIONSHIP RIDERS", "ROUND", etc.
          if (nameText.length >= 2 && nameText.length <= 40 && 
              !nameText.match(/^(CHAMPIONSHIP|RIDERS|ROUND|GP|ON SALE|RESULTS)/i) &&
              nameText.match(/[a-zA-Z]/)) {
            name = nameText;
          }
        }
      }
      
      // Fallback: använd alt-text
      if (!name && img.alt && img.alt.length > 2 && img.alt.length < 40) {
        name = img.alt.split(',')[0].trim();
      }
      
      parent = parent.parentElement;
      attempts++;
    }
    
    // Rensa namnet från onödiga ord
    if (name) {
      name = name.replace(/^(CHAMPIONSHIP|RIDERS|ROUND|GP|ON SALE|RESULTS|AFTER)\s+/i, '');
      name = name.replace(/\s+(CHAMPIONSHIP|RIDERS|ROUND|GP|ON SALE|RESULTS|AFTER)$/i, '');
    }
    
    // Om vi har ett nummer och bild, spara den
    if (number || name) {
      riders.push({
        name: name || `rider_${idx}`,
        number: number,
        imgUrl: img.src,
        width: width,
        height: height,
        index: idx
      });
    }
  });
  
  // Deduplicera baserat på bild-URL
  const seen = new Map();
  const unique = [];
  
  riders.forEach(r => {
    if (!seen.has(r.imgUrl)) {
      seen.set(r.imgUrl, true);
      unique.push(r);
    }
  });
  
  console.log(`\n✅ Hittade ${unique.length} unika riders med bilder`);
  
  if (unique.length === 0) {
    console.error('❌ Inga riders hittades!');
    console.log('💡 Tips: Scrolla ner på sidan för att ladda in fler riders, vänta några sekunder, kör sedan scriptet igen.');
    return;
  }
  
  // Visa tabell med alla hittade riders
  console.log('\n📋 Hittade riders:');
  console.table(unique.map((r, i) => ({
    '#': i + 1,
    Number: r.number || '?',
    Name: r.name,
    'Size': `${r.width}x${r.height}`,
    'Filename': `${r.number ? r.number + '_' : ''}${slugify(r.name)}.jpg`
  })));
  
  // Visa alla filnamn som kommer användas
  console.log('\n📝 Filnamn som kommer användas:');
  unique.forEach((r, i) => {
    const filename = `${r.number ? r.number + '_' : ''}${slugify(r.name)}.jpg`;
    console.log(`   ${i + 1}. ${filename}`);
  });
  
  // Fråga om nedladdning
  const proceed = confirm(
    `Hittade ${unique.length} riders med bilder.\n\n` +
    `Vill du ladda ner alla bilder?\n\n` +
    `Format: {nummer}_{namn}.jpg\n` +
    `Nedladdning sker med 400ms mellanrum mellan bilder.\n\n` +
    `Bilderna laddas ner till din Nedladdningar-mapp.`
  );
  
  if (!proceed) {
    console.log('❌ Avbruten av användare');
    return unique;
  }
  
  console.log(`\n📥 Laddar ner ${unique.length} bilder...`);
  console.log('💡 Om webbläsaren blockerar nedladdningar, klicka på "Tillåt alla" när den frågar.\n');
  
  let successCount = 0;
  let failCount = 0;
  
  // Ladda ner alla bilder
  for (let i = 0; i < unique.length; i++) {
    const rider = unique[i];
    const filename = `${rider.number ? rider.number + '_' : ''}${slugify(rider.name)}.jpg`;
    
    try {
      console.log(`   [${i + 1}/${unique.length}] Laddar ner: ${filename}`);
      
      // Hantera CORS och olika URL-typer
      let imageUrl = rider.imgUrl;
      
      // Om relativ URL, gör absolut
      if (imageUrl.startsWith('//')) {
        imageUrl = window.location.protocol + imageUrl;
      } else if (imageUrl.startsWith('/')) {
        imageUrl = window.location.origin + imageUrl;
      }
      
      const response = await fetch(imageUrl, { 
        mode: 'cors', 
        cache: 'no-cache',
        credentials: 'omit'
      });
      
      if (!response.ok) {
        console.warn(`   ⚠️ Kunde inte ladda ${filename}: HTTP ${response.status}`);
        failCount++;
        continue;
      }
      
      const blob = await response.blob();
      
      // Verifiera att det är en bild
      if (!blob.type.startsWith('image/')) {
        console.warn(`   ⚠️ ${filename} är inte en bild (type: ${blob.type})`);
        failCount++;
        continue;
      }
      
      // Ladda ner
      downloadBlob(blob, filename);
      successCount++;
      
      // Vänta mellan nedladdningar
      await new Promise(resolve => setTimeout(resolve, 400));
    } catch (err) {
      console.error(`   ❌ Fel vid nedladdning av ${filename}:`, err.message);
      failCount++;
    }
  }
  
  console.log(`\n✅ Klart!`);
  console.log(`   ✓ Lyckades: ${successCount}`);
  console.log(`   ✗ Misslyckades: ${failCount}`);
  
  if (successCount > 0) {
    console.log(`\n📋 Nästa steg:`);
    console.log(`   1. Gå till din Nedladdningar-mapp`);
    console.log(`   2. Markera alla .jpg filer som börjar med ett nummer (t.ex. 94_ken_roczen.jpg)`);
    console.log(`   3. Flytta dem till: C:\\projects\\MittFantasySpel\\static\\riders\\wsx\\`);
    console.log(`   4. Bilderna visas automatiskt i appen!`);
  }
  
  return unique;
})();

