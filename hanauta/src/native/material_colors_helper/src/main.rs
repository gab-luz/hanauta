use clap::Parser;
use image::GenericImageView;
use material_colors::{
    hct::Hct,
    quantize::quantizer::Quantizer,
    quantize::quantizer_celebi::QuantizerCelebi,
    scheme::content::SchemeContent,
    utils::color::{Argb, Rgb},
};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(name = "hanauta-material-colors", version, about = "Extract Material colors from artwork")]
struct Args {
    /// Input artwork image path
    #[arg(short, long)]
    input: PathBuf,

    /// Output JSON file path (default: stdout)
    #[arg(short, long)]
    output: Option<PathBuf>,

    /// Target size for color extraction (default: 128)
    #[arg(short, long, default_value = "128")]
    size: u32,
}

#[derive(Serialize, Deserialize, Debug)]
struct MaterialPalette {
    source: String,
    light: MaterialScheme,
    dark: MaterialScheme,
}

#[derive(Serialize, Deserialize, Debug)]
struct MaterialScheme {
    primary: String,
    on_primary: String,
    primary_container: String,
    on_primary_container: String,
    secondary: String,
    on_secondary: String,
    secondary_container: String,
    on_secondary_container: String,
    tertiary: String,
    on_tertiary: String,
    surface: String,
    on_surface: String,
    surface_variant: String,
    on_surface_variant: String,
    outline: String,
}

fn argb_to_hex(argb: Argb) -> String {
    format!("#{:02X}{:02X}{:02X}", argb.red, argb.green, argb.blue)
}

fn scheme_to_material(scheme: &SchemeContent) -> MaterialScheme {
    let s = &scheme.scheme;
    MaterialScheme {
        primary: argb_to_hex(s.primary()),
        on_primary: argb_to_hex(s.on_primary()),
        primary_container: argb_to_hex(s.primary_container()),
        on_primary_container: argb_to_hex(s.on_primary_container()),
        secondary: argb_to_hex(s.secondary()),
        on_secondary: argb_to_hex(s.on_secondary()),
        secondary_container: argb_to_hex(s.secondary_container()),
        on_secondary_container: argb_to_hex(s.on_secondary_container()),
        tertiary: argb_to_hex(s.tertiary()),
        on_tertiary: argb_to_hex(s.on_tertiary()),
        surface: argb_to_hex(s.surface()),
        on_surface: argb_to_hex(s.on_surface()),
        surface_variant: argb_to_hex(s.surface_variant()),
        on_surface_variant: argb_to_hex(s.on_surface_variant()),
        outline: argb_to_hex(s.outline()),
    }
}

fn extract_palette(image_path: &PathBuf, size: u32) -> anyhow::Result<MaterialPalette> {
    // Load and resize image
    let img = image::open(image_path)?;
    let resized = img.resize_exact(size, size, image::imageops::FilterType::Lanczos3);

    // Convert to Argb pixels for quantization
    let rgb_img = resized.to_rgb8();
    let pixels: Vec<Argb> = rgb_img
        .pixels()
        .map(|p| {
            let [r, g, b] = p.0;
            Rgb::new(r, g, b).into()
        })
        .collect();

    // Quantize colors to find dominant color
    let mut quantizer = QuantizerCelebi::default();
    let results = quantizer.quantize(&pixels, 128, None);

    // Get the dominant color as source (first color in the result)
    let source_color = results
        .color_to_count
        .keys()
        .next()
        .copied()
        .unwrap_or_else(|| Argb::new(255, 208, 188, 255));
    let source_hex = source_color.as_hex();

    // Create HCT from source color for scheme generation
    let source_hct = Hct::new(source_color);

    // Generate Material Content schemes for both light and dark
    let light_scheme = SchemeContent::new(source_hct, false, None);
    let dark_scheme = SchemeContent::new(source_hct, true, None);

    Ok(MaterialPalette {
        source: source_hex,
        light: scheme_to_material(&light_scheme),
        dark: scheme_to_material(&dark_scheme),
    })
}

fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    let palette = extract_palette(&args.input, args.size)?;

    let json = serde_json::to_string_pretty(&palette)?;

    if let Some(output) = args.output {
        std::fs::write(output, json)?;
    } else {
        println!("{}", json);
    }

    Ok(())
}
