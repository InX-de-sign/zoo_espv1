#!/usr/bin/env python3
"""
Extract class names and metadata from ONNX model
Usage: python extract_classes.py
"""

import onnx
import json

def extract_model_info(model_path):
    """Extract all useful information from ONNX model"""
    
    print(f"Loading model: {model_path}")
    print("=" * 70)
    
    try:
        model = onnx.load(model_path)
        
        # 1. Model metadata
        print("\n📋 MODEL METADATA:")
        print("-" * 70)
        if model.metadata_props:
            for prop in model.metadata_props:
                print(f"  {prop.key}: {prop.value}")
        else:
            print("  No metadata found")
        
        # 2. Input information
        print("\n📥 MODEL INPUTS:")
        print("-" * 70)
        for input_tensor in model.graph.input:
            print(f"  Name: {input_tensor.name}")
            shape = [dim.dim_value if dim.dim_value > 0 else 'dynamic' 
                    for dim in input_tensor.type.tensor_type.shape.dim]
            print(f"  Shape: {shape}")
            print(f"  Type: {input_tensor.type.tensor_type.elem_type}")
        
        # 3. Output information
        print("\n📤 MODEL OUTPUTS:")
        print("-" * 70)
        for output_tensor in model.graph.output:
            print(f"  Name: {output_tensor.name}")
            shape = [dim.dim_value if dim.dim_value > 0 else 'dynamic' 
                    for dim in output_tensor.type.tensor_type.shape.dim]
            print(f"  Shape: {shape}")
            print(f"  Type: {output_tensor.type.tensor_type.elem_type}")
        
        # 4. Try to extract class names from metadata
        print("\n🏷️  CLASS NAMES:")
        print("-" * 70)
        
        class_names = []
        
        # Method 1: Check metadata properties
        for prop in model.metadata_props:
            if 'names' in prop.key.lower() or 'classes' in prop.key.lower():
                try:
                    # Try to parse as JSON
                    class_names = json.loads(prop.value)
                    print(f"  Found in metadata (key: {prop.key}):")
                    break
                except:
                    # Try as comma-separated string
                    class_names = [name.strip() for name in prop.value.split(',')]
                    print(f"  Found in metadata (key: {prop.key}):")
                    break
        
        # Method 2: Check initializers (sometimes stored as constants)
        if not class_names:
            for initializer in model.graph.initializer:
                if 'names' in initializer.name.lower() or 'classes' in initializer.name.lower():
                    print(f"  Found in initializer: {initializer.name}")
                    # This is less common, but worth checking
        
        # Method 3: Check for common YOLO metadata locations
        if not class_names:
            print("  ⚠️  No class names found in standard metadata locations")
            print("  💡 Class names might be stored externally or in training config")
        
        # Display class names
        if class_names:
            if isinstance(class_names, dict):
                print("\n  Classes (dictionary format):")
                for idx, name in class_names.items():
                    print(f"    {idx}: {name}")
            else:
                print(f"\n  Total classes: {len(class_names)}")
                print("\n  Classes (list format):")
                for idx, name in enumerate(class_names):
                    print(f"    {idx}: {name}")
            
            # Save to file
            output_file = "model_classes.json"
            with open(output_file, 'w') as f:
                json.dump({
                    "classes": class_names if isinstance(class_names, list) else list(class_names.values()),
                    "num_classes": len(class_names),
                    "model_path": model_path
                }, f, indent=2)
            print(f"\n  ✅ Classes saved to: {output_file}")
        
        # 5. Model graph statistics
        print("\n📊 MODEL STATISTICS:")
        print("-" * 70)
        print(f"  Graph name: {model.graph.name}")
        print(f"  Number of nodes: {len(model.graph.node)}")
        print(f"  Number of initializers: {len(model.graph.initializer)}")
        print(f"  ONNX version: {model.opset_import[0].version if model.opset_import else 'unknown'}")
        
        print("\n" + "=" * 70)
        print("✅ Model analysis complete!")
        
        return class_names
        
    except FileNotFoundError:
        print(f"❌ Error: Model file not found: {model_path}")
        print("   Please make sure the file exists in the current directory")
        return None
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    model_path = "best_animal_v3.onnx"
    
    print("🔍 ONNX Model Class Extractor")
    print("=" * 70)
    
    classes = extract_model_info(model_path)
    
    if classes:
        print("\n✅ Success! You can now use these classes in your inference code.")
    else:
        print("\n⚠️  If class names weren't found in the model:")
        print("   1. Check your training config file (e.g., data.yaml)")
        print("   2. Look for a classes.txt or names.txt file")
        print("   3. Check your training script/notebook for class definitions")
        print("\nPlease share any of those files or manually list the animal classes.")