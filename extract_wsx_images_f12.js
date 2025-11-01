// F12 Console Script för WSX Race Images
// Kopiera och klistra in hela scriptet i F12 Console på worldsupercrosschampionship.com

(function() {
    console.log("=".repeat(60));
    console.log("WSX Race Images Extractor");
    console.log("=".repeat(60));
    
    const images = [];
    const seen = new Set();
    
    // Hitta alla bilder på sidan
    const allImages = document.querySelectorAll('img');
    const allElements = document.querySelectorAll('[style*="background-image"]');
    
    console.log(`\n[INFO] Hittade ${allImages.length} <img> taggar`);
    console.log(`[INFO] Hittade ${allElements.length} element med background-image\n`);
    
    // Process <img> taggar
    allImages.forEach((img, index) => {
        const sources = [];
        
        // Kolla src, data-src, etc
        ['src', 'data-src', 'data-lazy-src', 'data-original'].forEach(attr => {
            const val = img.getAttribute(attr);
            if (val && !seen.has(val)) {
                seen.add(val);
                sources.push({
                    attr: attr,
                    url: val.startsWith('http') ? val : new URL(val, window.location.href).href
                });
            }
        });
        
        // Kolla srcset
        const srcset = img.getAttribute('srcset');
        if (srcset) {
            srcset.split(',').forEach(item => {
                const url = item.trim().split(' ')[0];
                if (url && !seen.has(url)) {
                    seen.add(url);
                    const fullUrl = url.startsWith('http') ? url : new URL(url, window.location.href).href;
                    sources.push({
                        attr: 'srcset',
                        url: fullUrl
                    });
                }
            });
        }
        
        sources.forEach(source => {
            // Filtrera bort thumbnails och små bilder
            if (source.url.includes('thumb') || 
                source.url.includes('thumbnail') || 
                source.url.includes('icon') ||
                source.url.includes('logo') ||
                source.url.includes('avatar')) {
                return;
            }
            
            // Kolla bildstorlek från URL
            const sizeMatch = source.url.match(/(\d{3,4})x(\d{3,4})/);
            const width = sizeMatch ? parseInt(sizeMatch[1]) : 0;
            const height = sizeMatch ? parseInt(sizeMatch[2]) : 0;
            const maxSize = Math.max(width, height);
            
            // Bara ta bilder som är minst 600px (eller saknar dimensioner i URL)
            if (maxSize > 0 && maxSize < 600) {
                return;
            }
            
            // Hitta föräldrarcontainer för att se om det är i en race-container
            let container = img.closest('div, article, section');
            let containerText = '';
            let containerClasses = '';
            
            if (container) {
                containerText = container.textContent.trim().substring(0, 100).toLowerCase();
                containerClasses = Array.from(container.classList).join(' ');
            }
            
            // Försök identifiera race från container text eller URL
            const raceIdentifiers = {
                'buenos': 'Buenos Aires',
                'argentina': 'Buenos Aires',
                'canadian': 'Canadian GP',
                'canada': 'Canadian GP',
                'australian': 'Australian GP',
                'australia': 'Australian GP',
                'swedish': 'Swedish GP',
                'sweden': 'Swedish GP',
                'south african': 'South African GP',
                'south africa': 'South African GP'
            };
            
            let identifiedRace = '';
            const allText = (containerText + ' ' + source.url).toLowerCase();
            for (const [key, raceName] of Object.entries(raceIdentifiers)) {
                if (allText.includes(key)) {
                    identifiedRace = raceName;
                    break;
                }
            }
            
            images.push({
                url: source.url,
                attr: source.attr,
                width: width,
                height: height,
                maxSize: maxSize,
                alt: img.getAttribute('alt') || '',
                containerText: containerText.substring(0, 50),
                identifiedRace: identifiedRace,
                element: img
            });
        });
    });
    
    // Process background-image styles
    allElements.forEach(elem => {
        const style = elem.getAttribute('style') || '';
        const bgMatch = style.match(/url\(['"]?([^'"]+)['"]?\)/);
        
        if (bgMatch) {
            const url = bgMatch[1];
            const fullUrl = url.startsWith('http') ? url : new URL(url, window.location.href).href;
            
            if (!seen.has(fullUrl)) {
                seen.add(fullUrl);
                
                // Filtrera bort thumbnails
                if (fullUrl.includes('thumb') || 
                    fullUrl.includes('thumbnail') || 
                    fullUrl.includes('icon')) {
                    return;
                }
                
                const sizeMatch = fullUrl.match(/(\d{3,4})x(\d{3,4})/);
                const width = sizeMatch ? parseInt(sizeMatch[1]) : 0;
                const height = sizeMatch ? parseInt(sizeMatch[2]) : 0;
                const maxSize = Math.max(width, height);
                
                if (maxSize > 0 && maxSize < 600) {
                    return;
                }
                
                let containerText = '';
                let container = elem.closest('div, article, section');
                if (container) {
                    containerText = container.textContent.trim().substring(0, 100).toLowerCase();
                }
                
                const allText = (containerText + ' ' + fullUrl).toLowerCase();
                let identifiedRace = '';
                const raceIdentifiers = {
                    'buenos': 'Buenos Aires',
                    'argentina': 'Buenos Aires',
                    'canadian': 'Canadian GP',
                    'canada': 'Canadian GP',
                    'australian': 'Australian GP',
                    'australia': 'Australian GP',
                    'swedish': 'Swedish GP',
                    'sweden': 'Swedish GP',
                    'south african': 'South African GP',
                    'south africa': 'South African GP'
                };
                
                for (const [key, raceName] of Object.entries(raceIdentifiers)) {
                    if (allText.includes(key)) {
                        identifiedRace = raceName;
                        break;
                    }
                }
                
                images.push({
                    url: fullUrl,
                    attr: 'background-image',
                    width: width,
                    height: height,
                    maxSize: maxSize,
                    alt: '',
                    containerText: containerText.substring(0, 50),
                    identifiedRace: identifiedRace,
                    element: elem
                });
            }
        }
    });
    
    // Sortera efter storlek (största först)
    images.sort((a, b) => (b.maxSize || 0) - (a.maxSize || 0));
    
    console.log(`\n[RESULT] Hittade ${images.length} potentiella race-illustrationer:\n`);
    console.log("=".repeat(80));
    
    // Gruppera efter identifierad race
    const byRace = {};
    const unassigned = [];
    
    images.forEach((img, index) => {
        if (img.identifiedRace) {
            if (!byRace[img.identifiedRace]) {
                byRace[img.identifiedRace] = [];
            }
            byRace[img.identifiedRace].push(img);
        } else {
            unassigned.push(img);
        }
    });
    
    // Visa grupperade efter race
    Object.entries(byRace).forEach(([race, imgs]) => {
        console.log(`\n🏁 ${race} (${imgs.length} bilder):`);
        console.log("-".repeat(80));
        imgs.forEach((img, i) => {
            console.log(`  ${i + 1}. ${img.url}`);
            console.log(`     Size: ${img.width}x${img.height} (max: ${img.maxSize}px)`);
            console.log(`     Source: ${img.attr}`);
            if (img.alt) console.log(`     Alt: ${img.alt}`);
            console.log('');
        });
    });
    
    // Visa oidentifierade bilder
    if (unassigned.length > 0) {
        console.log(`\n❓ Oidentifierade bilder (${unassigned.length}):`);
        console.log("-".repeat(80));
        unassigned.forEach((img, i) => {
            console.log(`  ${i + 1}. ${img.url}`);
            console.log(`     Size: ${img.width}x${img.height} (max: ${img.maxSize}px)`);
            console.log(`     Source: ${img.attr}`);
            if (img.alt) console.log(`     Alt: ${img.alt}`);
            if (img.containerText) console.log(`     Container: ${img.containerText}...`);
            console.log('');
        });
    }
    
    console.log("=".repeat(80));
    console.log("\n💡 Tips:");
    console.log("- Kopiera URL:erna för de bilder du vill ha");
    console.log("- Högerklicka på bilden → Öppna bild i ny flik → Spara som");
    console.log("- Eller använd download_wsx_race_images_manual.py med URL:erna");
    console.log("\n📋 Snabb lista med bara URL:er:");
    console.log("-".repeat(80));
    [...Object.values(byRace).flat(), ...unassigned].forEach((img, i) => {
        console.log(`${i + 1}. ${img.url}`);
    });
    
    // Returnera objekt med bilderna så du kan använda dem i console
    return {
        byRace: byRace,
        unassigned: unassigned,
        all: [...Object.values(byRace).flat(), ...unassigned]
    };
})();

