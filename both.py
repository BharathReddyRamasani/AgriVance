from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-GUI backend
import matplotlib.pyplot as plt
import os

app = Flask(__name__)

# Load dataset
EXCEL_FILE = "Telangana_Agricultural_Prices.xlsx"

if os.path.exists(EXCEL_FILE) and os.access(EXCEL_FILE, os.R_OK):
    try:
        df = pd.read_excel(EXCEL_FILE, engine="openpyxl")
    except Exception as e:
        df = pd.DataFrame()
else:
    df = pd.DataFrame()

# Normalize DataFrame
if not df.empty:
    df.columns = df.columns.astype(str).str.strip().str.lower().str.replace(" ", "_")
    df.rename(columns={
        'min_price_(inr)': 'min_price',
        'max_price_(inr)': 'max_price',
        'crop_name': 'crop_name',
        'min price (inr)': 'min_price',
        'max price (inr)': 'max_price',
        'crop name': 'crop_name'
    }, inplace=True)

    text_columns = ['category', 'crop_name', 'location']
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str).str.strip().str.lower()

    if 'year' in df.columns:
        df['year'] = pd.to_numeric(df['year'], errors='coerce').fillna(0).astype(int)

    for col in ['category', 'crop_name', 'location']:
        if col in df.columns:
            df = df[df[col].notna() & (df[col] != '')]

    categories = sorted(df['category'].str.title().unique()) if 'category' in df.columns else []
    locations = sorted(df['location'].str.title().unique()) if 'location' in df.columns else []
    crops = sorted(df['crop_name'].str.title().unique()) if 'crop_name' in df.columns else []
    years = sorted(df['year'].unique()) if 'year' in df.columns else []
    years = [year for year in years if year > 0]
else:
    categories = locations = crops = years = []

REPORTS_DIR = os.path.join("static", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

def clear_old_reports():
    try:
        for file in os.listdir(REPORTS_DIR):
            os.remove(os.path.join(REPORTS_DIR, file))
    except Exception as e:
        pass

def generate_chart(chart_type, x_data, y_data, x_label, y_label, title, filename):
    try:
        if not x_data.size or not y_data.size:
            return None

        plt.figure(figsize=(10, 5))
        if chart_type == "bar":
            bars = plt.bar(x_data, y_data, color='#1f77b4', edgecolor='black')
            for bar in bars:
                plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f'{bar.get_height():.2f}',
                         ha='center', va='bottom', fontsize=10, fontweight="bold")
        elif chart_type == "line":
            plt.plot(x_data, y_data, marker='o', color='#2ca02c', linestyle='-', linewidth=2, markersize=8)

        plt.xlabel(x_label, fontsize=14, fontweight='bold')
        plt.ylabel(y_label, fontsize=14, fontweight='bold')
        plt.title(title, fontsize=16, fontweight='bold')
        plt.xticks(rotation=30, ha="right", fontsize=12)
        plt.yticks(fontsize=12)
        plt.grid(axis='y', linestyle='--', alpha=0.6)
        plt.tight_layout()

        report_path = os.path.join(REPORTS_DIR, filename)
        plt.savefig(report_path, dpi=300)
        plt.close()
        return f"/static/reports/{filename}"
    except Exception as e:
        return None

def generate_location_reports(category, location, year):
    try:
        required_cols = {'category', 'location', 'year', 'crop_name', 'min_price', 'max_price'}
        if not required_cols.issubset(df.columns):
            return None, None, None

        year = int(year)
        category = category.lower()
        location = location.lower()

        filtered_data = df[(df['category'] == category) & (df['location'] == location) & (df['year'] == year)]
        if filtered_data.empty:
            return None, None, None

        x_data = filtered_data["crop_name"].str.title()
        y_data = filtered_data["max_price"]

        clear_old_reports()
        bar_chart = generate_chart("bar", x_data, y_data, "Crop Name", "Max Price (₹)",
                                   f"Max Prices in {location.title()} ({category.title()}) - {year}",
                                   f"location_bar_{category}_{location}_{year}.png")
        line_chart = generate_chart("line", x_data, y_data, "Crop Name", "Max Price (₹)",
                                    f"Max Prices in {location.title()} ({category.title()}) - {year}",
                                    f"location_line_{category}_{location}_{year}.png")
        
        return bar_chart, line_chart, filtered_data[['category', 'location', 'crop_name', 'min_price', 'max_price']].to_dict('records')
    except Exception as e:
        return None, None, None

def generate_crop_reports(crop_name, year):
    try:
        required_cols = {'crop_name', 'year', 'location', 'min_price', 'max_price'}
        if not required_cols.issubset(df.columns):
            return None, None, None

        year = int(year)
        crop_name = crop_name.lower()

        filtered_data = df[(df['crop_name'] == crop_name) & (df['year'] == year)]
        if filtered_data.empty:
            return None, None, None

        x_data = filtered_data["location"].str.title()
        y_data = filtered_data["max_price"]

        clear_old_reports()
        bar_chart = generate_chart("bar", x_data, y_data, "Location", "Max Price (₹)",
                                   f"Max Prices of {crop_name.title()} - {year}",
                                   f"crop_bar_{crop_name}_{year}.png")
        line_chart = generate_chart("line", x_data, y_data, "Location", "Max Price (₹)",
                                    f"Max Prices of {crop_name.title()} - {year}",
                                    f"crop_line_{crop_name}_{year}.png")
        
        return bar_chart, line_chart, filtered_data[['category', 'location', 'crop_name', 'min_price', 'max_price']].to_dict('records')
    except Exception as e:
        return None, None, None

@app.route('/')
def index():
    return redirect(url_for('home'))

@app.route('/home')
def home():
    return render_template('index.html', categories=categories)

@app.route('/search', methods=['GET', 'POST'])
def search():
    selected_category = request.form.get('category', '').strip().lower()
    crops = []
    error = None

    if selected_category and 'category' in df.columns and 'crop_name' in df.columns:
        crops = sorted(df[df['category'] == selected_category]['crop_name'].str.title().unique())

    if request.method == 'POST' and request.form.get('crop_name'):
        crop_name = request.form['crop_name'].strip().lower()
        filtered_data = df[(df['category'] == selected_category) & (df['crop_name'] == crop_name) & (df['year'] == 2025)]
        
        if not filtered_data.empty:
            result_table = filtered_data[['category', 'location', 'crop_name', 'min_price', 'max_price']].to_dict('records')
            return render_template('search_results.html', result_table=result_table)
        else:
            error = f"⚠ No data found for Category: {selected_category.title()}, Crop: {crop_name.title()} in 2025."

    return render_template('search.html', categories=categories, crops=crops, 
                           selected_category=selected_category, error=error)

@app.route('/get_crops', methods=['POST'])
def get_crops():
    category = request.form.get('category', '').strip().lower()
    if category and 'category' in df.columns and 'crop_name' in df.columns:
        crops = sorted(df[df['category'] == category]['crop_name'].str.title().unique())
        return jsonify({'crops': crops})
    return jsonify({'crops': []})

@app.route('/compare', methods=['GET', 'POST'])
def compare():
    return render_template('compare.html', categories=categories, locations=locations, crops=crops, years=years)

@app.route('/compare-location', methods=['POST'])
def compare_location():
    category = request.form.get("category", "").strip().lower()
    location = request.form.get("location", "").strip().lower()
    year = request.form.get("year", "2025")

    bar_chart, line_chart, table_data = generate_location_reports(category, location, year)
    if bar_chart and line_chart and table_data:
        return render_template("results.html", bar_report=bar_chart, line_report=line_chart, table_data=table_data,
                               bar_filename=os.path.basename(bar_chart), line_filename=os.path.basename(line_chart))
    return render_template("compare.html", error="⚠ No data found for the selected filters.",
                           categories=categories, locations=locations, crops=crops, years=years)

@app.route('/compare-crop', methods=['POST'])
def compare_crop():
    crop_name = request.form.get("crop_name", "").strip().lower()
    year = request.form.get("year", "2025")

    bar_chart, line_chart, table_data = generate_crop_reports(crop_name, year)
    if bar_chart and line_chart and table_data:
        return render_template("results.html", bar_report=bar_chart, line_report=line_chart, table_data=table_data,
                               bar_filename=os.path.basename(bar_chart), line_filename=os.path.basename(line_chart))
    return render_template("compare.html", error="⚠ No data found for the selected filters.",
                           categories=categories, locations=locations, crops=crops, years=years)

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(REPORTS_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File not found", 404

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)