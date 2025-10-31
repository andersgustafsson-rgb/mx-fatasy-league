// Ladda ner alla WSX-förarbilder direkt till nedladdningsmappen
// Klistra in hela denna koden i F12-konsolen

(async function() {
  console.log('🚀 Startar WSX Image Downloader...');
  
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
  
  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    // Vänta lite innan vi frigör URL
    setTimeout(() => URL.revokeObjectURL(url), 100);
  }
  
  const riders = [];
  const allImages = Array.from(document.querySelectorAll('img'));
  
  console.log(`📸 Analyserar ${allImages.length} bilder...`);
  
  // Hitta alla stora bilder som ser ut som rider-foton
  allImages.forEach((img, idx) => {
    const width = img.naturalWidth || img.width || 0;
    const height = img.naturalHeight || img.height || 0;
    
    // Hoppa över små ikoner
    if (width < 100 || height < 100) return;
    if (img.src.includes('placeholder') || img.src.includes('logo') || img.src.includes('icon')) return;
    if (img.src.includes('data:image/svg')) return;
    if (!img.src || img.src.length < 20) return;
    
    // Hitta namn och nummer i närheten
    let parent = img.closest('article, section, div[class*="card"], div[class*="rider"], div[class*="Rider"]') || img.parentElement;
    let name = null;
    let number = null;
    let attempts = 0;
    
    // Strategi: Gå uppåt i DOM och leta efter text
    while (parent && attempts < 12) {
      const text = parent.textContent || '';
      
      // Hitta förarnummer (1-3 siffror, inte år)
      if (!number) {
        const nums = text.match(/\b([1-9]\d{0,2})\b/g);
        if (nums) {
          for (const n of nums) {
            const val = parseInt(n);
            // Filtrera bort årtal och stora nummer
            if (val >= 1 && val <= 999 && val < 1900) {
              number = val;
              break;
            }
          }
        }
      }
      
      // Hitta namn (text efter nummer, före komma/radbrytning)
      if (number && !name && text.includes(number.toString())) {
        const parts = text.split(number.toString());
        if (parts.length > 1) {
          // Ta text efter nummer
          for (let i = 1; i < parts.length; i++) {
            let candidate = parts[i].split(',')[0].split('\n')[0].trim();
            // Rensa bort onödiga ord
            candidate = candidate.replace(/^(CHAMPIONSHIP|RIDERS|ROUND|GP|ON SALE|RESULTS|AFTER|USA|USAUSA|Germany|France|Australia|Canada|Brazil|UK|Spain)\s+/i, '');
            candidate = candidate.replace(/\s+(CHAMPIONSHIP|RIDERS|ROUND|GP|ON SALE|RESULTS|AFTER|USA|USAUSA|Germany|France|Australia|Canada|Brazil|UK|Spain)$/i, '');
            
            // Kolla om det ser ut som ett namn
            if (candidate.length >= 2 && candidate.length <= 35 && 
                candidate.match(/^[a-zA-Z\s]+$/) && 
                !candidate.match(/^(CHAMPIONSHIP|RIDERS|ROUND|GP|BUENOS|AIRES|CITY|GOLD|COAST|VANCOUVER|CAPE|TOWN|STOCKHOLM|SWEDISH|SOUTH|AFRICAN|CANADIAN|AUSTRALIAN)/i)) {
              name = candidate;
              break;
            }
          }
        }
      }
      
      // Alternativ: leta efter h1-h5 eller element med "name" i class
      if (!name) {
        const nameEl = parent.querySelector('h1, h2, h3, h4, h5, [class*="name"], [class*="Name"], [class*="title"], [class*="Title"]');
        if (nameEl) {
          let nameText = nameEl.textContent.trim();
          nameText = nameText.split(',')[0].split('\n')[0].trim();
          // Filtrera bort rubriker och onödiga ord
          nameText = nameText.replace(/^(CHAMPIONSHIP|RIDERS|ROUND|GP|ON SALE|RESULTS|AFTER|USA|USAUSA|Germany|France|Australia|Canada|Brazil|UK|Spain|WORLD|SUPERCROSS|DEBUT|BACK|FOR|SEASON|WILDCARD|BUENOS|AIRES|CITY)\s+/i, '');
          nameText = nameText.replace(/\s+(CHAMPIONSHIP|RIDERS|ROUND|GP|ON SALE|RESULTS|AFTER|USA|USAUSA|Germany|France|Australia|Canada|Brazil|UK|Spain|WORLD|SUPERCROSS|DEBUT|BACK|FOR|SEASON|WILDCARD|BUENOS|AIRES|CITY)$/i, '');
          
          if (nameText.length >= 2 && nameText.length <= 35 && 
              nameText.match(/[a-zA-Z]/) &&
              !nameText.match(/^(CHAMPIONSHIP|RIDERS|ROUND|GP|BUENOS|AIRES|CITY|GOLD|COAST|VANCOUVER|CAPE|TOWN|STOCKHOLM|SWEDISH|SOUTH|AFRICAN|CANADIAN|AUSTRALIAN|WILDCARD|DEBUT|BACK|FOR|SEASON|WORLD|SUPERCROSS)/i)) {
            name = nameText;
            break;
          }
        }
      }
      
      parent = parent.parentElement;
      attempts++;
    }
    
    // Om vi har bild + namn eller nummer, spara den
    if ((name || number) && img.src && !img.src.startsWith('data:')) {
      riders.push({
        name: name || null,
        number: number,
        imgUrl: img.src,
        width: width,
        height: height
      });
    }
  });
  
  // Deduplicera
  const seen = new Map();
  const unique = [];
  
  riders.forEach(r => {
    const key = r.imgUrl;
    if (!seen.has(key)) {
      seen.set(key, true);
      unique.push(r);
    }
  });
  
  // Filtrera bort riders utan namn OCH nummer (förmodligen inte riders)
  const validRiders = unique.filter(r => r.name && r.name.length >= 2);
  
  console.log(`\n✅ Hittade ${validRiders.length} riders med namn och bild`);
  
  if (validRiders.length === 0) {
    console.error('❌ Inga riders hittades!');
    console.log('💡 Tips: Scrolla hela vägen ner på sidan, vänta några sekunder att JS laddar klart, kör sedan scriptet igen.');
    return;
  }
  
  // Visa vad som hittades
  console.log('\n📋 Hittade riders:');
  console.table(validRiders.map((r, i) => ({
    '#': i + 1,
    Number: r.number || '?',
    Name: r.name,
    'Size': `${r.width}x${r.height}`,
    'Filename': `${r.number ? r.number + '_' : ''}${slugify(r.name)}.jpg`
  })));
  
  // Bekräfta nedladdning
  const proceed = confirm(
    `Hittade ${validRiders.length} riders med bilder.\n\n` +
    `Detta kommer ladda ner ${validRiders.length} bilder till din Nedladdningar-mapp.\n\n` +
    `Format: {nummer}_{namn}.jpg\n\n` +
    `Webbläsaren kan fråga om du vill tillåta flera nedladdningar.\n` +
    `Klicka "Tillåt" eller "Tillåt alla" om den frågar.\n\n` +
    `Fortätt?`
  );
  
  if (!proceed) {
    console.log('❌ Avbruten');
    return;
  }
  
  console.log(`\n📥 Laddar ner ${validRiders.length} bilder...`);
  console.log('💡 Om webbläsaren blockerar nedladdningar, klicka "Tillåt alla" när den frågar.\n');
  
  let success = 0;
  let failed = 0;
  
  // Ladda ner alla bilder med fördröjning
  for (let i = 0; i < validRiders.length; i++) {
    const rider = validRiders[i];
    const filename = `${rider.number ? rider.number + '_' : ''}${slugify(rider.name)}.jpg`;
    
    try {
      console.log(`   [${i + 1}/${validRiders.length}] ${filename}...`, end='');
      
      // Hantera olika URL-typer
      let imageUrl = rider.imgUrl;
      if (imageUrl.startsWith('//')) {
        imageUrl = window.location.protocol + imageUrl;
      } else if (imageUrl.startsWith('/')) {
        imageUrl = window.location.origin + imageUrl;
      }
      
      // Ladda ner bilden
      const response = await fetch(imageUrl, {
        mode: 'cors',
        cache: 'no-cache',
        credentials: 'omit'
      });
      
      if (!response.ok) {
        console.log(` ⚠️ HTTP ${response.status}`);
        failed++;
        continue;
      }
      
      const blob = await response.blob();
      
      // Verifiera att det är en bild
      if (!blob.type.startsWith('image/')) {
        console.log(` ⚠️ Inte en bild (${blob.type})`);
        failed++;
        continue;
      }
      
      // Ladda ner
      downloadBlob(blob, filename);
      console.log(` ✅`);
      success++;
      
      // Vänta mellan nedladdningar (för att inte överbelasta)
      await new Promise(resolve => setTimeout(resolve, 500));
      
    } catch (err) {
      console.log(` ❌ Fel: ${err.message}`);
      failed++;
    }
  }
  
  console.log(`\n✅ Klart!`);
  console.log(`   ✓ Lyckades: ${success}`);
  console.log(`   ✗ Misslyckades: ${failed}`);
  
  if (success > 0) {
    console.log(`\n📋 Nästa steg:`);
    console.log(`   1. Gå till din Nedladdningar-mapp`);
    console.log(`   2. Markera alla .jpg filer som börjar med ett nummer`);
    console.log(`   3. Flytta dem till: C:\\projects\\MittFantasySpel\\static\\riders\\wsx\\`);
    console.log(`   4. Bilderna visas automatiskt i appen! 🎉`);
  }
  
  return validRiders;
})();

